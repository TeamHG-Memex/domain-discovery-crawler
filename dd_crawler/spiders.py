import csv
import time
from typing import Iterator

import autopager
from deepdeep.predictor import LinkClassifier
from scrapy import Spider, Request
from scrapy.http.response import Response
from scrapy.http.response.html import HtmlResponse
from scrapy.linkextractors import LinkExtractor
from scrapy_cdr.utils import text_cdr_item

from .utils import dont_increase_depth, setup_profiling


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
            self.response_log.writerow(
                ['{:.3f}'.format(time.time()),
                 response.url,
                 str(response.meta.get('depth', '')),
                 str(response.request.priority),
                 ])
            self.response_log_file.flush()

    def page_item(self, response: HtmlResponse):
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

    def __init__(self, clf=None, **kwargs):
        if clf:  # can be empty if we juss want to get queue stats
            self.clf = LinkClassifier.load(clf)
        super().__init__(**kwargs)

    def start_requests(self):
        initial_priority = 10 * self.settings.getfloat('DD_PRIORITY_MULTIPLIER')
        for request in super().start_requests():
            request.priority = initial_priority
            yield request

    def extract_urls(self, response: HtmlResponse) -> Iterator[Request]:
        urls = self.clf.extract_urls(response.text, response.url)
        for score, url in urls:
            priority = int(
                score * self.settings.getfloat('DD_PRIORITY_MULTIPLIER'))
            yield Request(url, priority=priority)
