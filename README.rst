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

Start DB worker that reads incoming log::

    python -m frontera.worker.db --config dd_crawler.frontera.worker_settings --no-incoming

Start DB workers that generate new batches::

    python -m frontera.worker.db --config dd_crawler.frontera.worker_settings --no-batches

Start strategy workers::

    python -m frontera.worker.strategy \
        --config dd_crawler.frontera.worker_settings \
        --strategy frontera.worker.strategies.bfs.CrawlingStrategy \
        --partition-id 0

Start spider workers::

    scrapy crawl dd_crawler -s SPIDER_PARTITION_ID=0 -s SEEDS_SOURCE=seeds.txt
    scrapy crawl dd_crawler -s SPIDER_PARTITION_ID=1

