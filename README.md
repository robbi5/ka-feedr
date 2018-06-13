# kA-feedr: publish feeds to twitter, with delay

kA-feedr checks feeds that you specify for new content and queues posts on your twitter account.

### Features

* can check multiple feed urls
* [RFC 5005 - feed paging](https://tools.ietf.org/html/rfc5005) support
* shortens tweet text to (currently) 280 chars
* appends … to text if it got cut off
* closes open parantheses if text got cut off
* tweets multiple new feed items with a delay of one minute in between (see `DELAY_BETWEEN_TWEETS`)
* configurable with environment variables
* `SIMULATE` mode which suppresses tweeting
* `NEWER_THAN` setting for working with already existing feeds
* and more. the source is short, read it :)

### Usage
Use python3. Install dependencies with `pip install -r requirements.txt`.

We're using kA-feedr for multiple [kleineAnfragen](https://kleineanfragen.de) twitter accounts as cronjobs:

```
CONSUMER_KEY="..."
CONSUMER_SECRET="..."
NEWER_THAN="2018-06-06T00:00:00Z"
#SIMULATE=1

* * * * * DATABASE="/srv/feedr/db/anfragen_bt.sqlite3" ACCESS_TOKEN="..." ACCESS_SECRET="..." /srv/feedr/bin/python3 /srv/feedr/feedr.py "https://kleineanfragen.de/bundestag.atom?feedformat=twitter" >> /srv/feedr/log/anfragen_bt.log

* * * * * DATABASE="/srv/feedr/db/anfragen_hh.sqlite3" ACCESS_TOKEN="..." ACCESS_SECRET="..." /srv/feedr/bin/python3 /srv/feedr/feedr.py "https://kleineanfragen.de/hamburg.atom?feedformat=twitter" >> /srv/feedr/log/anfragen_hh.log
```


### Thanks
Thanks to [@housed](https://github.com/housed) for the inspiration with [feedr](https://github.com/housed/feedr). This project was roughly based on it and is now a complete rewrite.