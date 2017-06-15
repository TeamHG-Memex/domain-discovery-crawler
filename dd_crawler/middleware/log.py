import csv
import time

from scrapy.exceptions import NotConfigured
from scrapy.http.response.html import HtmlResponse
from scrapy_cdr import CDRItem

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
        self.log_writer = csv.writer(self.log_file)
        self.relevancy_threshold = relevancy_threshold

    @classmethod
    def from_crawler(cls, crawler):
        log_path = crawler.settings.get('RESPONSE_LOG_FILE')
        if not log_path:
            raise NotConfigured('RESPONSE_LOG_FILE not defined')
        threshold = crawler.settings.getfloat('PAGE_RELEVANCY_THRESHOLD', 0.5)
        return cls(log_path=log_path, relevancy_threshold=threshold)

    def process_spider_output(self, response, result, spider):
        for item in result:
            if isinstance(item, CDRItem):
                self.log_item(item, response)
            yield item

    def log_item(self, item: CDRItem, response: HtmlResponse):
        self.n_crawled += 1
        domain = get_domain(item['url'])
        self.domains.add(domain)
        score = item.get('metadata', {}).get('page_score', 0.)
        if score is not None:
            self.total_score += score
            if score > self.relevancy_threshold:
                self.relevant_domains.add(domain)
        log_entry = [
            '{:.3f}'.format(time.time()),
            response.url,
            response.meta.get('depth', ''),
            response.request.priority,
            '{:.3f}'.format(score),
            '{:.3f}'.format(self.total_score),
            self.n_crawled,
            len(self.domains),
            len(self.relevant_domains),
        ]
        self.log_writer.writerow([str(x) for x in log_entry])
        self.log_file.flush()
