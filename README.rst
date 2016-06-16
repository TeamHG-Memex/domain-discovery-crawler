Domain Discovery Crawler
========================

Install
-------

Use Python 3.5::

    pip install -r requirements.txt
    pip install -e .


Usage
-----

Start ZeroMQ broker::

    python -m frontera.contrib.messagebus.zeromq.broker

Start DB worker::

    python -m frontera.worker.db --config dd_crawler.frontera.worker_settings

Start spider workers::

    scrapy crawl dd_crawler -s SEEDS_SOURCE=seeds.txt -s SPIDER_PARTITION_ID=0
    scrapy crawl dd_crawler -s SPIDER_PARTITION_ID=1

