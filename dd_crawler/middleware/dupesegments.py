# -*- coding: utf-8 -*-
from __future__ import absolute_import

import scrapy
from scrapy.exceptions import NotConfigured
from scrapy.utils.httpobj import urlparse_cached


class DupeSegmentsMiddleware:
    """
    Spider middleware which drops requests with a large number of duplicate
    path segments in URL. Such URLs are usually incorrect. To enable it,
    add DupeSegmentsMiddleware to SPIDER_MIDDLEWARES and set
    MAX_DUPLICATE_PATH_SEGMENTS option::

    MAX_DUPLICATE_PATH_SEGMENTS = 5  # false positives should be rare
    SPIDER_MIDDLEWARES = {
        'dd_crawler.middleware.dupesegments.DupeSegmentsMiddleware': 750,
    }

    """
    def __init__(self, max_duplicate_segments, stats):
        self.max_duplicate_segments = max_duplicate_segments
        self.stats = stats

    @classmethod
    def from_crawler(cls, crawler):
        segments = crawler.settings.getint('MAX_DUPLICATE_PATH_SEGMENTS')
        if not segments:
            raise NotConfigured()
        return cls(segments, crawler.stats)

    def process_spider_output(self, response, result, spider):
        for el in result:
            if isinstance(el, scrapy.Request):
                path = urlparse_cached(el).path
                if num_duplicate_segments(path) > self.max_duplicate_segments:
                    self.stats.inc_value('DupeSegmentsMiddleware/dropped')
                    continue
            yield el


def num_duplicate_segments(path):
    """
    >>> num_duplicate_segments("")
    0
    >>> num_duplicate_segments("/")
    0
    >>> num_duplicate_segments("/foo/")
    0
    >>> num_duplicate_segments("/foo/foo")
    1
    >>> num_duplicate_segments("/foo/foo/bar/foo")
    2
    """
    segments = [p for p in path.split('/') if p]
    return len(segments) - len(set(segments))
