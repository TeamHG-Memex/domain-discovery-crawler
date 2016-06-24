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

For redis connection settings, refer to scrapy-redis docs.


Using docker
------------

Build dd-crawler image::

    docker build -t dd-crawler .

Start everything (this will take seeds from local ``seeds.txt``)::

    docker-compose up

Crawled items will be written in CDR format to the local ``./out`` folder,
one ``items_[0-n].jl`` file for each spider worker.


Docker system setup
-------------------

Apart from installing docker, you might want to tell it to store data in
a different location: redis persists queue to disk, and it can be quite big.
To do so on Ubuntu, edit ``/etc/default/docker``, setting the path to
desired storage directory via ``-g`` option, e.g.
``DOCKER_OPTS="-g /data/docker"``, and restart docker daemon.
