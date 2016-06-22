import re
from contextlib import contextmanager
from urllib.parse import urlsplit

from scrapy import Spider, Request
from scrapy.http.response.html import HtmlResponse
from scrapy.linkextractors import LinkExtractor
from scrapy_cdr.utils import text_cdr_item


class GeneralSpider(Spider):
    name = 'dd_crawler'

    def __init__(self, *args, **kwargs):
        super(GeneralSpider, self).__init__(*args, **kwargs)
        self.le = LinkExtractor()
        self.domain_limit = False
        self.reset_depth = False

    def start_requests(self):
        self.domain_limit = self.settings.getbool('DOMAIN_LIMIT')
        self.reset_depth = self.settings.getbool('RESET_DEPTH')
        if self.settings.get('SEEDS'):
            with open(self.settings.get('SEEDS')) as f:
                urls = [line.strip() for line in f]
            for url in urls:
                yield Request(url)
        else:
            super().start_requests()

    def parse(self, response):
        if not isinstance(response, HtmlResponse):
            return

        domain = _get_domain(response.request.url)
        for link in self.le.extract_links(response):
            different_domain = _get_domain(link.url) == domain
            if not (self.domain_limit and different_domain):
                with _reset_depth_if(
                        self.reset_depth and different_domain, response):
                    yield Request(url=link.url)

        yield text_cdr_item(
            response,
            crawler_name=self.settings.get('CDR_CRAWLER'),
            team_name=self.settings.get('CDR_TEAM'),
        )


def _get_domain(url):
    domain = urlsplit(url).netloc
    return re.sub(r'^www\.', '', domain)


@contextmanager
def _reset_depth_if(reset, response):
    depth = response.meta.get('depth')
    if reset:
        response.meta['depth'] = 0
    try:
        yield
    finally:
        if reset:
            response.meta['depth'] = depth
