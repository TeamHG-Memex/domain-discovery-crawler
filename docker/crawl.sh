#!/bin/bash

set -e

# Start caching DNS server
dnsmasq

echo 'Waiting for redis...'
while ! redis-cli -h redis get some-key-tocheck-if-redis-is-ready; do sleep 0.1; done

# Crawl
scrapy crawl dd_crawler -s REDIS_HOST=redis $*