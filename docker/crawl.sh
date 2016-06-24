#!/bin/bash

set -e

# Start caching DNS server
dnsmasq

# Crawl
scrapy crawl dd_crawler $*