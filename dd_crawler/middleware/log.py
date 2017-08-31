import json
import time
from typing import Dict

from scrapy.exceptions import NotConfigured
from scrapy.http.response.html import HtmlResponse
from scrapy_cdr import CDRItem

from dd_crawler.utils import get_domain


class RequestLogMiddleware:
    def __init__(self, *, jl_logger, relevancy_threshold: float):
        # This are per-worker values, while stats values updated in
        # dd_crawler.queue are global.
        self.domains = set()
        self.relevant_domains = set()
        self.total_score = 0.
        self.n_crawled = 0
        self.jl_logger = jl_logger
        self.relevancy_threshold = relevancy_threshold

    @classmethod
    def from_crawler(cls, crawler) -> 'RequestLogMiddleware':
        log_path = crawler.settings.get('RESPONSE_LOG_FILE')
        if not log_path:
            raise NotConfigured('RESPONSE_LOG_FILE not defined')
        jl_logger = get_jl_logger(log_path)
        threshold = crawler.settings.getfloat('PAGE_RELEVANCY_THRESHOLD', 0.5)
        return cls(jl_logger=jl_logger, relevancy_threshold=threshold)

    def process_spider_output(self, response, result, spider):
        for item in result:
            if isinstance(item, CDRItem):
                self.log_item(item, response)
            yield item

    def log_item(self, item: CDRItem, response: HtmlResponse):
        self.n_crawled += 1
        domain = get_domain(item['url'])
        self.domains.add(domain)
        metadata = item.get('metadata', {})
        score = metadata.get('page_score', 0.)
        if score is not None:
            self.total_score += score
            if score > self.relevancy_threshold:
                self.relevant_domains.add(domain)
        log_entry = {
            'time': time.time(),
            'url': response.url,
            'id': metadata.get('id'),
            'parent': metadata.get('parent'),
            'depth': response.meta.get('depth', ''),
            'priority': response.request.priority,
            'score': score,
            'total_score': self.total_score,
            'n_crawled': self.n_crawled,
            'n_domains': len(self.domains),
            'n_relevant_domains': len(self.relevant_domains),
        }
        self.jl_logger.write_entry(log_entry)


class JsonLinesLogger:
    def __init__(self, log_path):
        self._log_file = open(log_path, 'at')

    def write_entry(self, log_entry: Dict):
        json.dump(log_entry, self._log_file)
        self._log_file.write('\n')
        self._log_file.flush()


_loggers = {}


def get_jl_logger(log_path):
    if log_path not in _loggers:
        _loggers[log_path] = JsonLinesLogger(log_path)
    return _loggers[log_path]
