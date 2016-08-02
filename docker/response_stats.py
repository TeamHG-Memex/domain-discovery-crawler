#!/usr/bin/env python3

from utils import run_in_docker


def main():
    run_in_docker(
        'scrapy response_stats -o /out/response-stats /out/*.csv')


if __name__ == '__main__':
    main()
