#!/bin/bash

set -e

# Start caching DNS server
dnsmasq

echo 'Waiting for redis...'
# First wait while it's up
while ! redis-cli -h redis get some-key-to-check-if-redis-is-ready; do sleep 0.1; done
# Next, it can be up but still loading, so we grep for "LOADING"
while redis-cli -h redis get some-key-to-check-if-redis-is-ready | grep -q LOADING; do sleep 0.1; done

hostname=`hostname`

echo "Crawling (see logs at /out/${hostname}.log)"
scrapy crawl -o /out/${hostname}_items.jl -s REDIS_HOST=redis -s LOG_FILE=/out/${hostname}.log $*
# Run a profiled crawl instead:
# python -m vmprof -o /out/${hostname}.vmprof docker/exec_scrapy.py crawl -o /out/${hostname}_items.jl -s REDIS_HOST=redis -s LOG_FILE=/out/${hostname}.log $*
