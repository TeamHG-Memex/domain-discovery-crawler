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

Start focused crawl with some seeds::

    scrapy crawl deepdeep -a seeds=seeds.txt \
        -a clf=Q.joblib -a page_clf=page_clf.joblib \
        -o gzip:out/items.jl

Start other workers without specifying seeds.

Arguments:

- ``seeds``: a text file with seed urls, one url on a line.
- ``clf``: Q-model (link classifier) from deep-deep.
- ``page_clf`` (optional): page classifier: must take text or a dict with
  "text" and "url" keys as input, and return page score (probability of the
  page being relevant). This argument is required if ``QUEUE_MAX_RELEVANT_DOMAINS``
  is set, but is useful even without it,
  in order to check how well the crawl is going.
- ``classifier_input`` (optiona, default is ``text``):
  should be ``text`` if ``page_clf`` takes text as input,
  or ``text_url`` if ``page_clf`` takes a dict with "text" and "url" keys
  as input.
- ``login_credentials`` (optional): path to a file with login credentials
  in JSON: a list of dicts with "url", "login" and "password" fields.

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
  relevant are selected according to sum of squares of relevant page scores.
- ``PAGE_RELEVANCY_THRESHOLD`` - a threshold when page (and thus the domain)
  is considered relevant, which is used when ``QUEUE_MAX_RELEVANT_DOMAINS`` is set.
- ``STATS_CLASS`` - set to ``'scrapy_statsd.statscollectors.StatsDStatsCollector'``
  in order to push scrapy stats to statsd for spider monitoring.
  Set ``STATSD_HOST`` and, optionally, ``STATSD_PORT``.
- ``RESPONSE_LOG_FILE`` - path to spider stats log in json lines format
  (see ``dd_crawler.middleware.log.RequestLogMiddleware.log_item``).
- ``HTTP_PROXY``, ``HTTPS_PROXY``: set to enable onion crawling via given proxy.
  The proxy will be used only for domains ending with ".onion".
- ``FILES_STORE``: all media items would be downloaded and saved to ``FILES_STORE``.
  S3 and filesystem supported, refer to scrapy docs.
- ``AUTOLOGIN_ENABLED`` - set to enable autologin support (see a separate section
  below).
- ``AUTOLOGIN_URL`` - set autologin HTTP API url.

For redis connection settings, refer to scrapy-redis docs.

To start a breadth-first crawl without deep-deep::

    scrapy crawl dd_crawler -a seeds=seeds.txt -o out/items.jl

To export items to a .gz archive use ``gzip:`` scheme::

    scrapy crawl... -o gzip:out/items.jl

To get a summary of queue stats and export full stats to json,
run (passing extra settings as needed)::

    scrapy queue_stats dd_crawler -o stats.json

To get a summary of response speed,
set ``RESPONSE_LOG_FILE`` setting during crawling, and use
(assuming log files end with .log.jl)::

    scrapy response_stat out/*.log.jl

You can also specify ``-o`` or ``--output`` argument to save charts to html
file instead of showing them.

Profiling is done using `vmprof <https://vmprof.readthedocs.io>`_.
Pass ``-a profile=basepath`` to the crawler, and then send ``SIGUSR1`` to start
and stop profiling. Result will be in ``basepath_N.vmprof`` file.


Autologin support
+++++++++++++++++

When autologin is enabled (``AUTOLOGIN_ENABLED`` is set), each domain is checked
for login forms - results of the checks are written to ``RESPONSE_LOG_FILE``
(into the ``has_login_form`` field), and stored in Redis.
If credentials are added via the ``scrapy login`` command, they are
added to redis, and an attempt to log in to the site is
be made. If successful, the crawl of this domain will continue while logged in.
Result of this attempt and current login state is written into
``login_success`` field in ``RESPONSE_LOG_FILE``.


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


Development
-----------

In order to run tests, you need
to install packages from ``tests/requirements.txt``,
and have  ``redis-server`` and
``autologin-http-api`` (https://github.com/TeamHG-Memex/autologin/) running.

Run tests with ``pytest``::

    py.test tests/

----

.. image:: https://hyperiongray.s3.amazonaws.com/define-hg.svg
	:target: https://www.hyperiongray.com/?pk_campaign=github&pk_kwd=domain-discovery-crawler
	:alt: define hyperiongray
