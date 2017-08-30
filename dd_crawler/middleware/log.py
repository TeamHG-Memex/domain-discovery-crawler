import json
import time
from typing import Dict

from scrapy.exceptions import NotConfigured
from scrapy.http.response.html import HtmlResponse
from scrapy_cdr import CDRItem

from dd_crawler.signals import queues_changed, domain_status_opened
from dd_crawler.queue import BaseRequestQueue
from dd_crawler.utils import get_domain


class RequestLogMiddleware:
    def __init__(self, *, log_path: str, relevancy_threshold: float):
        # This are per-worker values, while stats values updated in
        # dd_crawler.queue are global.
        self.domains = set()
        self.relevant_domains = set()
        self.total_score = 0.
        self.n_crawled = 0
        self.log_file = open(log_path, 'at')
        self.relevancy_threshold = relevancy_threshold
        self.domain_status = None
        self.domains_with_open_queues = None
        self.prev_domain_state = None

    @classmethod
    def from_crawler(cls, crawler) -> 'RequestLogMiddleware':
        log_path = crawler.settings.get('RESPONSE_LOG_FILE')
        if not log_path:
            raise NotConfigured('RESPONSE_LOG_FILE not defined')
        threshold = crawler.settings.getfloat('PAGE_RELEVANCY_THRESHOLD', 0.5)
        mw = cls(log_path=log_path, relevancy_threshold=threshold)
        if crawler.settings.getbool('DOMAIN_LIMIT'):
            crawler.signals.connect(mw.on_queues_changed, queues_changed)
            crawler.signals.connect(
                mw.on_domain_status_opened, domain_status_opened)
        return mw

    def process_spider_output(self, response, result, spider):
        for item in result:
            if isinstance(item, CDRItem):
                self.log_item(item, response)
            yield item

    def on_queues_changed(self, queue: BaseRequestQueue):
        self.domains_with_open_queues = [
            queue.queue_key_domain(q) for q in queue.get_queues()]

    def on_domain_status_opened(self, status: Dict):
        self.domain_status = status

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
        if self.domain_status is not None:
            in_flight = {d for d, rqs in self.domain_status['in_flight'].items()
                         if rqs}
            open_queues = set(self.domains_with_open_queues or []) | in_flight
            all_domains = (open_queues |
                           self.domain_status['have_failures'] |
                           self.domain_status['have_successes'])
            failed_domains = (self.domain_status['have_failures'] -
                              self.domain_status['have_successes'])
            domain_state = {}
            for domain in all_domains:
                if domain in failed_domains:
                    state = 'failed'
                elif domain not in open_queues:
                    state = 'finished'
                else:
                    state = 'running'
                domain_state[domain] = state
            if domain_state != self.prev_domain_state:
                log_entry['domain_state'] = domain_state
                self.prev_domain_state = domain_state
        json.dump(log_entry, self.log_file)
        self.log_file.write('\n')
        self.log_file.flush()
