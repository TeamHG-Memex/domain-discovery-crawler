#!/bin/bash

set -e

partition_id=$1
shift

# Start caching DNS server
dnsmasq

# Crawl
scrapy crawl dd_crawler -s SPIDER_PARTITION_ID=${partition_id} -o /dd_crawler/out/items_${partition_id}.jl $*
