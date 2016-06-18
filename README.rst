Domain Discovery Crawler
========================

Install
-------

Use Python 3.5::

    pip install -r requirements.txt
    pip install -e .


Using docker
------------

Build dd-crawler image::

    docker build -t dd-crawler .

Start everything (this will take seeds from local ``seeds.txt``)::

    docker-compose up

Currently it will fail to start properly for the first time due to db starting
slower, so you have to stop it and start once again.

Crawled items will be written in CDR format to the local ``./out`` folder,
one ``items_[0-n].jl`` file for each spider worker.

The number of spider workers in ``docker-compose.yml``
must match ``SPIDER_FEED_PARTITIONS`` in ``dd_crawler.frontera.common_settings``.

TODO:

- use strategy workers and two separate db workers
- expose broker and sql database (to allow connection from external machines)
- add or generate an "external" docker-compose
- do something with numbers of spider and strategy workers
