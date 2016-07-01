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

Usage
-----

Start crawl with some seeds::

    scrapy crawl dd_crawler -a seeds=seeds.txt

Start other workers without specifying seeds.

Settings:

- ``DOMAIN_LIMIT`` (``True`` by default): stay within start domains
- ``RESET_DEPTH`` (``False`` by default): reset depth to 0 when going to new
  domains (this allows to get a lot of new domains quickly)
- ``AUTOPAGER`` - prioritize pagination links

For redis connection settings, refer to scrapy-redis docs.

To get a summary of queue stats and export full stats to json,
run (passing extra settings as needed)::

    scrapy queue_stats dd_crawler -o stats.json


Profiling
---------

Profiling is done using `vmprof <https://vmprof.readthedocs.io>`_.
Pass ``-a profile=basepath`` to the crawler, and then send ``SIGUSR1`` to start
and stop profiling. Result will be in ``basepath_N.vmprof`` file.


Using docker
------------

Build dd-crawler image::

    docker build -t dd-crawler .

Start everything (this will take seeds from local ``./seeds.txt``, and
deep-deep model from ``./Q.joblib``)::

    docker-compose up -d

After that, you can set desired number of crawler workers (4 in this example) with::

    docker-compose scale crawler=4

Crawled items will be written in CDR format to the local ``./out`` folder,
one ``${hostname}_items.jl`` file for each crawler worker, and logs will
be written to ``${hostname}.log`` files.

You can get queue with ``./docker/queue_stats.py``
(or ``./docker/queue_stats.py  -o /out/stats.json`` if you want detailed output
into local ``./out`` folder).

Profiling is enabled in the docker container, so you just need to send
``SIGUSR1`` to scrapy process in order to start/stop profiling. Result will be
written to ``./out/${hostname}_N.vmprof``.


Docker system setup on Ubuntu 14.04
-----------------------------------

Install docker engine::

    sudo apt-key adv --keyserver hkp://p80.pool.sks-keyservers.net:80 \
                     --recv-keys 58118E89F3A912897C070ADBF76221572C52609D
    echo "deb https://apt.dockerproject.org/repo ubuntu-trusty main" \
      | sudo tee /etc/apt/sources.list.d/docker.list
    sudo apt-get update
    sudo apt-get install docker-engine

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
