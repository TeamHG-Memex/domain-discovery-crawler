#!/bin/bash

set -e

# Start caching DNS server
dnsmasq

echo 'Waiting for redis...'
while ! nc -w 1 -z redis 6379; do sleep 0.1; done

# Crawl
scrapy crawl dd_crawler -s REDIS_HOST=redis $*