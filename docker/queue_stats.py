#!/usr/bin/env python3

from dd_crawler.utils import run_in_docker


def main():
    run_in_docker('scrapy queue_stats deepdeep -s REDIS_HOST=redis')


if __name__ == '__main__':
    main()
