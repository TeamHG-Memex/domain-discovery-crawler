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
    MAX_DUPLICATE_PATH_SEGMENTS and/or MAX_DUPLICATE_QUERY_SEGMENTS options::

        # false positives should be rare with these values
        MAX_DUPLICATE_PATH_SEGMENTS = 5
        MAX_DUPLICATE_QUERY_SEGMENTS = 3
        SPIDER_MIDDLEWARES = {
            'dd_crawler.middleware.dupesegments.DupeSegmentsMiddleware': 750,
        }

    """
    def __init__(self,
                 max_path_segments: int,
                 max_query_segments: int,
                 stats) -> None:
        self.max_path_segments = max_path_segments
        self.max_query_segments = max_query_segments
        self.stats = stats

    @classmethod
    def from_crawler(cls, crawler):
        path_segments = crawler.settings.getint('MAX_DUPLICATE_PATH_SEGMENTS')
        query_segments = crawler.settings.getint('MAX_DUPLICATE_QUERY_SEGMENTS')
        if not (path_segments or query_segments):
            raise NotConfigured()
        return cls(path_segments, query_segments, crawler.stats)

    def process_spider_output(self, response, result, spider):
        for el in result:
            if isinstance(el, scrapy.Request):
                p = urlparse_cached(el)
                if _too_many_segments(p.path, self.max_path_segments, '/'):
                    self.stats.inc_value('DupeSegmentsMiddleware/dropped/path')
                    continue
                if _too_many_segments(p.query, self.max_query_segments, '&'):
                    self.stats.inc_value('DupeSegmentsMiddleware/dropped/query')
                    continue
            yield el


def num_duplicate_segments(text: str, sep: str='/') -> int:
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
    segments = [p for p in text.split(sep) if p]
    return len(segments) - len(set(segments))


def _too_many_segments(text, max_segments, sep):
    if max_segments and num_duplicate_segments(text, sep) > max_segments:
        return True
    return False
