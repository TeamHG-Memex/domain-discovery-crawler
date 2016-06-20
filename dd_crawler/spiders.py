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

    def parse(self, response):
        if not isinstance(response, HtmlResponse):
            return

        domain = _get_domain(response.url)

        for link in self.le.extract_links(response):
            # This is a "soft" domain check: we are not guaranteed to stay
            # within one domain, but do not follow out-domain links. This
            # means that we only change domain during redirects.
            if _get_domain(link.url) == domain:
                r = Request(url=link.url)
                r.meta.update(link_text=link.text)
                yield r

        yield text_cdr_item(
            response,
            crawler_name=self.settings.get('CDR_CRAWLER'),
            team_name=self.settings.get('CDR_TEAM'),
        )


def _get_domain(url):
    domain = urlsplit(url).netloc
    return re.sub(r'^www\.', '', domain)
