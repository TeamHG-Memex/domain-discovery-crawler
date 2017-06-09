Domain Discovery Crawler
========================

This is a scrapy crawler that uses Redis queues and link classification model from
deep-deep for large-scale focused crawls.

Preferred installation and running method is using docker,
but you can also run it without it, which is described first.

.. contents::

Install
-------

Use Python 3.5::

    pip install -r requirements.txt
    pip install -e .

You also need to have ``redis-server`` running
(you might want to tweak persistence options to make it less frequent or turn
it off completely).

Usage
-----

Start crawl with some seeds::

    scrapy crawl deepdeep -a seeds=seeds.txt \
        -a clf=Q.joblib -a page_clf=page_clf.joblib \
        -o gzip:out/items.jl

Start other workers without specifying seeds.

``Q.clf`` is a link classifier from deep-deep,
and ``page_clf.joblib`` is an sklearn model for page classification that takes
text (if ``classifier_input`` spider argument is at deafult ``text`` value)
or dict with "text" and "url" keys (if ``classifier_input`` is ``text_url``)
as input. ``page_clf.joblib`` is strictly required only when
``QUEUE_MAX_RELEVANT_DOMAINS`` is set,
but is still useful in order to check how well the crawl is going.

To start a breadth-first crawl without deep-deep::

    scrapy crawl dd_crawler -a seeds=seeds.txt -o out/items.jl

Settings:

- ``DOMAIN_LIMIT`` (``False`` by default): stay within start domains
- ``RESET_DEPTH`` (``False`` by default): reset depth to 0 when going to new
  domains (this allows to get a lot of new domains quickly)
- ``AUTOPAGER`` - prioritize pagination links (if not using deep-deep)
- ``QUEUE_SCORES_LOG`` - log full queue selection process for batch softmax queue
  (written in ``.jl.gz`` format).
- ``QUEUE_MAX_DOMAINS`` - max number of domains (disabled due to a bug)
- ``QUEUE_MAX_RELEVANT_DOMAINS`` - max number of relevant domains: domain is considered
  relevant if some page from that domain is considered relevant by ``page_clf``.
  Crawler drops all irrelevant domains after gathering
  the specified number of relevant ones (but not earlier than
  ``RESTRICT_DELAY``, 1 hour by default), and does not go to new domains any more.
  If more relevant domains were discovered before ``RESTRICT_DELAY``, most
  relevant are selected accoring to sum of squares of relevant page scores.
  If ``QUEUE_MAX_RELEVANT_DOMAINS``, only hints (see below) are left after
  ``RESTRICT_DELAY``.
- ``PAGE_RELEVANCY_THRESHOLD`` - a threshold when page (and thus the domain)
  is considered relevant, which is used when ``QUEUE_MAX_RELEVANT_DOMAINS`` is set.
- ``STATS_CLASS`` - set to ``'scrapy_statsd.statscollectors.StatsDStatsCollector'``
  in order to push scrapy stats to statsd for spider monitoring.
  Set ``STATSD_HOST`` and, optionally, ``STATSD_PORT``.
- ``RESPONSE_LOG_FILE`` - path to spider stats log in csv format
  (see ``dd_crawler.middleware.log.RequestLogMiddleware.log_item``).
- ``HTTP_PROXY``, ``HTTPS_PROXY``: set to enable onion crawling via given proxy.
  The proxy will be used only for domains ending with ".onion".

When ``QUEUE_MAX_RELEVANT_DOMAINS`` is defined (even if it's zero),
hints are also taken into account.
They are stored as utf8-encoded urls in ``BaseRequestQueue.hints_key`` redis set.
After broad crawling for ``RESTRICT_DELAY`` seconds, only hints and
top ``QUEUE_MAX_RELEVANT_DOMAINS`` domains are crawled.

For redis connection settings, refer to scrapy-redis docs.

To export items to a .gz archive use ``gzip:`` scheme::

    scrapy crawl dd_crawler -a seeds=seeds.txt -o gzip:out/items.jl

To get a summary of queue stats and export full stats to json,
run (passing extra settings as needed)::

    scrapy queue_stats dd_crawler -o stats.json

To get a summary of response speed, set ``RESPONSE_LOG_FILE`` setting, and use::

    scrapy response_stat out/*.csv

You can also specify ``-o`` or ``--output`` argument to save charts to html
file instead of showing them.

Profiling is done using `vmprof <https://vmprof.readthedocs.io>`_.
Pass ``-a profile=basepath`` to the crawler, and then send ``SIGUSR1`` to start
and stop profiling. Result will be in ``basepath_N.vmprof`` file.


Using docker
------------

Build dd-crawler image::

    docker build -t dd-crawler .

Start everything (this will take seeds from local ``./seeds.txt``,
deep-deep model from ``./Q.joblib`` and page relevancy model from ``./page_clf.joblib``)::

    docker-compose up -d

After that, you can set desired number of crawler workers (4 in this example) with::

    docker-compose scale crawler=4

Crawled items will be written in CDR format to the local ``./out`` folder,
one ``${hostname}_items.jl.gz`` file for each crawler worker, logs will
be written to ``${hostname}.log`` files, and downloaded urls with page scores
to ``${hostname}.csv`` files.

If you want to change default settings (described above),
edit the ``docker-compose.yml`` file.

You can get queue stats with ``./docker/queue_stats.py``
(or ``./docker/queue_stats.py  -o /out/stats.json`` if you want detailed output
into local ``./out`` folder).

You can get response speed stats with ``./docker/response_stats.py``, which
writes some stats to the terminal and charts to ``./out/response_stats.html``.

Profiling is enabled in the docker container, so you just need to send
``SIGUSR1`` to scrapy process in order to start/stop profiling. Result will be
written to ``./out/${hostname}_N.vmprof``. An example::

    docker exec -it domaindiscoverycrawler_crawler_1 /bin/bash
    kill -10 `ps aux | grep scrapy | grep -v grep | awk '{print $2}'`
    kill -10 `ps aux | grep scrapy | grep -v grep | awk '{print $2}'`


Docker system setup on Ubuntu 16.04
-----------------------------------

Install docker engine::

    sudo apt-get install docker.io

Add yourself to the docker group (optional, requires re-login)::

    sudo usermod -aG docker <yourname>

Install docker-compose::

    sudo apt-get install python-pip
    sudo -H pip install docker-compose

Apart from installing docker, you might want to tell it to store data in
a different location: redis persists queue to disk, and it can be quite big.
To do so on Ubuntu, edit ``/etc/default/docker``, setting the path to
desired storage directory via ``-g`` option, e.g.
``DOCKER_OPTS="-g /data/docker"``, and restart docker daemon.
