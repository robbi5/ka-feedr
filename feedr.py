#!/usr/bin/env python
# -*- coding: utf-8 -*-

import tweepy
import feedparser
import sqlite3
import time
import os
import sys
from datetime import datetime, timedelta

#
# feedr.py
# - reads a feed, queues it and pushes the entries
#   a bit delay between each other to twitter
# Usage:
#   feedr.py <feed-url> <feed-url> <feed-url> <...>
#
# Environment Variables:
#   * SIMULATE
#   * DATABASE
#   * CONSUMER_KEY
#   * CONSUMER_SECRET
#   * ACCESS_TOKEN
#   * ACCESS_SECRET
#   * NEWER_THAN = '2002-09-07T00:00:00Z' (iso, only utc)
#
# Supports paginated feeds. Aborts searching for new entries after
# two pages of already known ones.
#

BOOLEAN_TRUE_STRINGS = ('true', 't', 'y', 'yes', '1')
DB_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

SIMULATE = os.getenv('SIMULATE', 'false').lower() in BOOLEAN_TRUE_STRINGS
DELAY_BETWEEN_TWEETS = timedelta(minutes=1)
db_file = os.getenv('DATABASE', './feedr.db')
DATABASE = os.path.join(os.path.dirname(__file__), db_file)
nt = os.getenv('NEWER_THAN', '2002-09-07T00:00:00Z')

NEWER_THAN = datetime.strptime(nt, '%Y-%m-%dT%H:%M:%SZ')
FEEDS = sys.argv[1:]

# Define the net max length of the text portion of a tweet
# See https://api.twitter.com/1.1/help/configuration.json
TWEET_MAX_LENGTH = 280
TWEET_URL_LENGTH = 23
TWEET_TEXT_LENGTH = TWEET_MAX_LENGTH - TWEET_URL_LENGTH - 1  # space


def init_twitter_api():
    CONSUMER_KEY = os.environ['CONSUMER_KEY']
    CONSUMER_SECRET = os.environ['CONSUMER_SECRET']
    ACCESS_TOKEN = os.environ['ACCESS_TOKEN']
    ACCESS_SECRET = os.environ['ACCESS_SECRET']

    auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
    auth.set_access_token(ACCESS_TOKEN, ACCESS_SECRET)
    return tweepy.API(auth)


def handle_entry(api, cursor, entry):
    cursor.execute('SELECT * FROM feed_content WHERE url=?', (entry.link,))
    if cursor.fetchall():
        return False

    data = (
        entry.link,
        entry.title,
        time.strftime(DB_DATE_FORMAT, entry.updated_parsed),)
    cursor.execute(
        'INSERT INTO feed_content (`url`, `title`, `seen_at`) VALUES (?,?,?)',
        data)

    if entry.updated_parsed < NEWER_THAN.timetuple():
        return False

    pubdate = entry.updated_parsed
    tweet_body = entry.title
    if len(entry.title) > TWEET_TEXT_LENGTH:
        tweet_body = entry.title[:TWEET_TEXT_LENGTH-2] + '…'
    if "(" in tweet_body and ")" not in tweet_body:
        tweet_body = entry.title[:TWEET_TEXT_LENGTH-3] + '…)'
    tweet_text = "%s %s" % (tweet_body, entry.link)

    add_to_queue(cursor, pubdate, tweet_text)

    return True


def add_to_queue(cursor, pubdate, text):
    now = datetime.now()
    next_delivery = now + DELAY_BETWEEN_TWEETS
    cursor.execute(
        'SELECT deliver_at FROM queue ORDER BY deliver_at DESC LIMIT 1')
    n = cursor.fetchone()
    if n:
        parsed_date = datetime.strptime(n['deliver_at'], DB_DATE_FORMAT)
        next_delivery = parsed_date + DELAY_BETWEEN_TWEETS
    if next_delivery < datetime.now():
        next_delivery = now + DELAY_BETWEEN_TWEETS
    data = (text, next_delivery.strftime(DB_DATE_FORMAT))
    print('action=queue date={} queuedfor={} pub={} text="{}"'.format(
        datetime.now().isoformat(),
        next_delivery.isoformat(),
        datetime(*pubdate[:6]).isoformat(),
        text))
    cursor.execute(
        'INSERT INTO queue (`text`, `deliver_at`) VALUES (?,?)',
        data)


def send_queued_tweets(api, conn, cursor):
    data = (datetime.now().strftime(DB_DATE_FORMAT), )
    cursor.execute(
        'SELECT * FROM queue WHERE delivered_at IS NULL AND deliver_at < ?',
        data)
    queue = cursor.fetchall()
    if not queue:
        return False
    for entry in queue:
        handle_queue_entry(api, cursor, entry)
        conn.commit()


def handle_queue_entry(api, cursor, entry):
    parsed_delivery = datetime.strptime(entry['deliver_at'], DB_DATE_FORMAT)
    print('action=tweet date={} queuedfor={} text="{}"'.format(
        datetime.now().isoformat(),
        parsed_delivery.isoformat(),
        entry['text']))
    formatted_now = datetime.now().strftime(DB_DATE_FORMAT)
    data = (formatted_now, entry['text'], parsed_delivery)

    if SIMULATE:
        return

    try:
        api.update_status(entry['text'])
    except tweepy.error.TweepError as e:
        print('action=tweet date={} error="{}" text="{}"'.format(
            datetime.now().isoformat(),
            e,
            entry['text']
            ), file=sys.stderr)
    else:
        cursor.execute(
            'UPDATE queue SET delivered_at=? WHERE text=? AND deliver_at=?',
            data)


def parse_feed_recursive(api, conn, cursor, url, known=0):
    parsed_feed = feedparser.parse(url)
    all_known = False

    entries = parsed_feed.entries
    # handle older entries first
    entries.reverse()
    for entry in entries:
        all_known |= not handle_entry(api, cursor, entry)
        conn.commit()

    # get next page
    next_feed_url = None
    if parsed_feed.feed and parsed_feed.feed.links:
        for link in parsed_feed.feed.links:
            if not link.rel == 'next':
                continue
            next_feed_url = link.href
            break

    if next_feed_url:
        if all_known:
            known = known + 1
        if known < 2:
            parse_feed_recursive(api, conn, cursor, next_feed_url, known)


def run(api):
    # create database file if it doesn't exist
    open(DATABASE, 'a').close()

    conn = sqlite3.connect(DATABASE, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        'CREATE TABLE IF NOT EXISTS feed_content (' +
        '`url`,`title`,`seen_at`' +
        ')')
    c.execute(
        'CREATE TABLE IF NOT EXISTS queue (' +
        '`text`,`deliver_at`,`delivered_at`' +
        ')')

    if len(FEEDS) == 0:
        print("Warning: you didn't provide any feeds as arguments. " +
              "sending queued tweets only", file=sys.stderr)

    for feed_url in FEEDS:
        parse_feed_recursive(api, conn, c, feed_url)

    send_queued_tweets(api, conn, c)
    conn.close()


if __name__ == '__main__':
    api = init_twitter_api()
    run(api)
