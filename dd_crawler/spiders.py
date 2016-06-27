from contextlib import contextmanager

from scrapy import Spider, Request
from scrapy.http.response.html import HtmlResponse
from scrapy.linkextractors import LinkExtractor
from scrapy_cdr.utils import text_cdr_item

from .utils import get_domain


class GeneralSpider(Spider):
    name = 'dd_crawler'

    def __init__(self, *args, **kwargs):
        super(GeneralSpider, self).__init__(*args, **kwargs)
        self.le = LinkExtractor()

    def start_requests(self):
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

        for link in self.le.extract_links(response):
            yield Request(url=link.url)

        yield text_cdr_item(
            response,
            crawler_name=self.settings.get('CDR_CRAWLER'),
            team_name=self.settings.get('CDR_TEAM'),
            metadata={
                'depth': response.meta.get('depth'),
            },
        )
