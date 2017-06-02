from functools import lru_cache
from typing import Iterator, List

import autopager
from deepdeep.predictor import LinkClassifier
from scrapy import Spider, Request, Item
from scrapy.exceptions import NotConfigured
from scrapy.http.response import Response
from scrapy.http.response.html import HtmlResponse
from scrapy.linkextractors import LinkExtractor
from scrapy_cdr.utils import text_cdr_item
import statsd

from .utils import dont_increase_depth, setup_profiling, PageClassifier


class GeneralSpider(Spider):
    name = 'dd_crawler'

    def __init__(self, seeds=None, profile=None):
        super().__init__()
        self.le = LinkExtractor(canonicalize=False)
        if seeds:
            with open(seeds) as f:
                self.start_urls = [line.strip() for line in f]
        if profile:
            setup_profiling(profile)

    def parse(self, response: Response):
        if not isinstance(response, HtmlResponse):
            return
        yield from self.extract_urls(response)
        yield self.page_item(response)
        stats = self.crawler.stats
        # To have a number of scraped items in statsd for the **current** crawl
        # (item_scraped_count is incr-ed, so we can not use it across crawls).
        stats.set_value('item_scraped_current_crawl',
                        stats.get_value('item_scraped_count', 0))

    def extract_urls(self, response: HtmlResponse) -> Iterator[Request]:
        if self.settings.getbool('AUTOPAGER'):
            for url in autopager.urls(response):
                with dont_increase_depth(response):
                    yield Request(url=url)
        for link in self.le.extract_links(response):
            yield Request(url=link.url)

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

    def __init__(self, clf=None, page_clf=None, classifier_input='text',
                 **kwargs):
        if clf:  # can be empty if we just want to get queue stats
            self.link_clf = LinkClassifier.load(clf)
        self.page_clf = PageClassifier(
            page_clf, classifier_input=classifier_input) if page_clf else None
        super().__init__(**kwargs)

    def start_requests(self):
        if not self.page_clf and self.settings.get('QUEUE_MAX_RELEVANT_DOMAINS'):
            raise NotConfigured('Pass page_clf to spider')
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
        return self.page_clf.get_score(html=response.text, url=response.url)

    @property
    def queue(self):
        try:
            return self.crawler.engine.slot.scheduler.queue
        except AttributeError:
            return None

    def extract_urls(self, response: HtmlResponse) -> Iterator[Request]:
        urls = self.link_clf.extract_urls_from_response(response)
        if self.page_clf:
            page_score = self.page_score(response)
            if self.statsd_client:
                self.statsd_client.timing(
                    'dd_crawler.page_score', 1000 * page_score)
            threshold = self.settings.getfloat('PAGE_RELEVANCY_THRESHOLD', 0.5)
            if page_score > threshold:
                self.queue.page_is_relevant(response.url)
        for score, url in urls:
            priority = int(
                score * self.settings.getfloat('DD_PRIORITY_MULTIPLIER'))
            yield Request(url, priority=priority)

    @property
    def statsd_client(self):
        if not hasattr(self, '_statsd_client'):
            s = self.settings
            if 'StatsDStatsCollector' in s.get('STATS_CLASS', ''):
                self._statsd_client = statsd.StatsClient(
                    host=s.get('STATSD_HOST', 'localhost'),
                    port=s.getint('STATSD_PORT', 8125),
                    prefix=s.get('STATSD_PREFIX', None))
            else:
                self._statsd_client = None
        return self._statsd_client

    def page_item(self, response: HtmlResponse) -> Item:
        item = super().page_item(response)
        if self.page_clf:
            item['metadata']['page_score'] = self.page_score(response)
        return item
