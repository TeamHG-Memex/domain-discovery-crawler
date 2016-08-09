import csv
from functools import lru_cache
import time
from typing import Iterator, List

import autopager
from deepdeep.predictor import LinkClassifier
from scrapy import Spider, Request, Item
from scrapy.http.response import Response
from scrapy.http.response.html import HtmlResponse
from scrapy.linkextractors import LinkExtractor
from scrapy_cdr.utils import text_cdr_item

from .utils import dont_increase_depth, setup_profiling, PageClassifier


class GeneralSpider(Spider):
    name = 'dd_crawler'

    def __init__(self, seeds=None, profile=None, response_log=None):
        super().__init__()
        self.le = LinkExtractor(canonicalize=False)
        if seeds:
            with open(seeds) as f:
                self.start_urls = [line.strip() for line in f]
        if profile:
            setup_profiling(profile)
        if response_log:
            self.response_log_file = open(response_log, 'a')
            self.response_log = csv.writer(self.response_log_file)
        else:
            self.response_log = None

    def parse(self, response: Response):
        if not isinstance(response, HtmlResponse):
            return
        yield from self.extract_urls(response)
        yield self.page_item(response)
        self.log_response(response)

    def extract_urls(self, response: HtmlResponse) -> Iterator[Request]:
        if self.settings.getbool('AUTOPAGER'):
            for url in autopager.urls(response):
                with dont_increase_depth(response):
                    yield Request(url=url)
        for link in self.le.extract_links(response):
            yield Request(url=link.url)

    def log_response(self, response: HtmlResponse):
        if self.response_log:
            self.response_log.writerow(self.response_log_item(response))
            self.response_log_file.flush()

    def response_log_item(self, response: HtmlResponse) -> List[str]:
        return ['{:.3f}'.format(time.time()),
                response.url,
                str(response.meta.get('depth', '')),
                str(response.request.priority),
                ]

    def page_item(self, response: HtmlResponse) -> Item:
        return text_cdr_item(
            response,
            crawler_name=self.settings.get('CDR_CRAWLER'),
            team_name=self.settings.get('CDR_TEAM'),
            metadata={
                'depth': response.meta.get('depth'),
                'priority': response.request.priority,
            },
        )


class DeepDeepSpider(GeneralSpider):
    name = 'deepdeep'

    def __init__(self, clf=None, page_clf=None, **kwargs):
        if clf:  # can be empty if we just want to get queue stats
            self.link_clf = LinkClassifier.load(clf)
        if page_clf:
            self.page_clf = PageClassifier(page_clf)
        super().__init__(**kwargs)

    def start_requests(self):
        initial_priority = int(
            10 * self.settings.getfloat('DD_PRIORITY_MULTIPLIER'))
        for request in super().start_requests():
            request.priority = initial_priority
            if self.queue is not None:
                self.queue.push(request)
            else:
                yield request

    @lru_cache(maxsize=1)
    def page_score(self, response: HtmlResponse) -> float:
        return self.page_clf.get_score(response.text)

    @property
    def queue(self):
        try:
            return self.crawler.engine.slot.scheduler.queue
        except AttributeError:
            return None

    def extract_urls(self, response: HtmlResponse) -> Iterator[Request]:
        urls = self.link_clf.extract_urls(response.text, response.url)
        page_score = self.page_score(response)
        page_is_relevant = page_score > 0.5
        if page_is_relevant:
            self.queue.page_is_relevant(response.url)
        for score, url in urls:
            priority = int(
                score * self.settings.getfloat('DD_PRIORITY_MULTIPLIER'))
            yield Request(url, priority=priority,
                          meta={'page_is_relevant': page_is_relevant})

    def page_item(self, response: HtmlResponse) -> Item:
        item = super().page_item(response)
        item['extracted_metadata']['page_score'] = self.page_score(response)
        return item

    def response_log_item(self, response: HtmlResponse) -> List[str]:
        item = super().response_log_item(response)
        item.append(str(self.page_score(response)))
        return item
