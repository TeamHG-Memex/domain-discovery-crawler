Domain Discovery Crawler
========================

Install
-------

Use Python 3.5::

    pip install -r requirements.txt
    pip install -e .


Using docker (does not work currently)
--------------------------------------

Build dd-crawler image::

    docker build -t dd-crawler .

Start everything (this will take seeds from local ``seeds.txt``)::

    docker-compose up

Crawled items will be written in CDR format to the local ``./out`` folder,
one ``items_[0-n].jl`` file for each spider worker.
