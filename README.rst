Domain Discovery Crawler
========================

Install
-------

Use Python 3.5::

    pip install -r requirements.txt
    pip install -e .

You also need to have ``redis-server`` running
(you might want to tweak persistence options to make it less frequent or turn
it off completely).

Start crawl with some seeds::

    scrapy crawl dd_crawler -s SEEDS=seeds.txt

Start other workers without specifying seeds.

Settings:

- ``DOMAIN_LIMIT`` (``True`` by default): stay within start domains
- ``RESET_DEPTH`` (``False`` by default): reset depth to 0 when going to new
  domains (this allows to get a lot of new domains quickly)
- ``QUEUE_CACHE_TIME`` (1 second by default) - time to cache the queues for.
 Set to higher values with more domains.


Using docker (does not work currently)
--------------------------------------

Build dd-crawler image::

    docker build -t dd-crawler .

Start everything (this will take seeds from local ``seeds.txt``)::

    docker-compose up

Crawled items will be written in CDR format to the local ``./out`` folder,
one ``items_[0-n].jl`` file for each spider worker.
