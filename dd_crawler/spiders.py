import base64
from functools import lru_cache
import hashlib
from typing import Iterator, Optional, Union

import autopager
from deepdeep.predictor import LinkClassifier
from scrapy import Spider, Request, Item
from scrapy.exceptions import NotConfigured
from scrapy.http.response import Response
from scrapy.http.response.html import HtmlResponse
from scrapy.linkextractors import LinkExtractor
from scrapy_cdr.utils import text_cdr_item
import statsd

from .queue import BaseRequestQueue
from .utils import dont_increase_depth, setup_profiling, PageClassifier


class BaseSpider(Spider):
    name = 'dd_crawler'

    def __init__(self, seeds=None, profile=None):
        super().__init__()
        self.le = LinkExtractor(canonicalize=False)
        self.files_le = LinkExtractor(deny_extensions=[], canonicalize=False)
        self.images_le = LinkExtractor(
            tags=['img'], attrs=['src'], deny_extensions=[], canonicalize=False)
        if seeds:
            with open(seeds) as f:
                self.start_urls = [line.strip() for line in f]
        if profile:
            setup_profiling(profile)

    def parse(self, response: Response):
        if not isinstance(response, HtmlResponse):
            return
        yield from self.extract_requests(response)
        yield self.page_item(response)
        stats = self.crawler.stats
        # To have a number of scraped items in statsd for the **current** crawl
        # (item_scraped_count is incr-ed, so we can not use it across crawls).
        stats.set_value('item_scraped_current_crawl',
                        stats.get_value('item_scraped_count', 0))

    def extract_requests(self, response: HtmlResponse) -> Iterator[Request]:
        if self.settings.getbool('AUTOPAGER'):
            for url in autopager.urls(response):
                with dont_increase_depth(response):
                    yield self._request(url, response)
        for link in self.le.extract_links(response):
            yield self._request(link.url, response)

    def _request(self, url: str, response: HtmlResponse, priority=0) -> Request:
        return Request(
            url=url,
            priority=priority,
            meta={'parent': _url_hash(response.url, as_bytes=True)},
        )

    def page_item(self, response: HtmlResponse) -> Item:
        media_urls = []
        get_urls = lambda le: (link.url for link in le.extract_links(response))
        if self.settings.get('FILES_STORE'):
            media_urls.extend(get_urls(self.images_le))
            media_urls.extend(set(get_urls(self.files_le)) - set(get_urls(self.le)))
        return text_cdr_item(
            response,
            crawler_name=self.settings.get('CDR_CRAWLER'),
            team_name=self.settings.get('CDR_TEAM'),
            objects=media_urls,
            metadata={
                'id': _url_hash(response.url, as_bytes=False),
                'depth': response.meta.get('depth'),
                'priority': response.request.priority,
                'parent': _url_hash_as_str(response.meta.get('parent')),
            },
        )


def _url_hash(url: str, *, as_bytes: bool) -> Union[str, bytes]:
    url_hash = hashlib.md5(url.encode('utf8')).digest()
    if not as_bytes:
        url_hash = _url_hash_as_str(url_hash)
    return url_hash


def _url_hash_as_str(url_hash: Optional[bytes]) -> Optional[str]:
    if url_hash is not None:
        return base64.b64encode(url_hash).decode('ascii')


class DeepDeepSpider(BaseSpider):
    name = 'deepdeep'

    def __init__(self, clf=None, page_clf=None, classifier_input='text', hints=None,
                 **kwargs):
        if clf:  # can be empty if we just want to get queue stats
            self.link_clf = LinkClassifier.load(clf)
        self.page_clf = PageClassifier(
            page_clf, classifier_input=classifier_input) if page_clf else None
        if hints:
            with open(hints) as f:
                self.hint_urls = [line.strip() for line in f]
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
    def queue(self) -> Optional[BaseRequestQueue]:
        try:
            return self.crawler.engine.slot.scheduler.queue
        except AttributeError:
            return None

    def extract_requests(self, response: HtmlResponse) -> Iterator[Request]:
        urls = self.link_clf.extract_urls_from_response(response)
        if self.page_clf:
            page_score = self.page_score(response)
            if self.statsd_client:
                self.statsd_client.timing(
                    'dd_crawler.page_score', 1000 * page_score)
            threshold = self.settings.getfloat('PAGE_RELEVANCY_THRESHOLD', 0.5)
            if page_score > threshold:
                self.queue.page_is_relevant(response.url, page_score)
        for score, url in urls:
            priority = int(
                score * self.settings.getfloat('DD_PRIORITY_MULTIPLIER'))
            yield self._request(url, response, priority=priority)

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
