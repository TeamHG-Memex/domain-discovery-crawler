import re
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

    def start_requests(self):
        self.domain_limit = self.settings.getbool('DOMAIN_LIMIT')
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
            if not self.domain_limit or _get_domain(link.url) == domain:
                yield Request(url=link.url)

        yield text_cdr_item(
            response,
            crawler_name=self.settings.get('CDR_CRAWLER'),
            team_name=self.settings.get('CDR_TEAM'),
        )


def _get_domain(url):
    domain = urlsplit(url).netloc
    return re.sub(r'^www\.', '', domain)
