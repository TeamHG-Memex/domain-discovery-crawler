#!/bin/bash

set -e

# Start caching DNS server
dnsmasq

echo 'Waiting for redis...'
while ! redis-cli -h redis get some-key-tocheck-if-redis-is-ready; do sleep 0.1; done

hostname=`hostname`

echo 'Crawling'
scrapy crawl dd_crawler -o /out/${hostname}_items.jl -s REDIS_HOST=redis -s LOG_FILE=/out/${hostname}.log $*