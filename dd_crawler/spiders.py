import autopager
from deepdeep.predictor import LinkClassifier
from scrapy import Spider, Request
from scrapy.http.response.html import HtmlResponse
from scrapy.linkextractors import LinkExtractor
from scrapy_cdr.utils import text_cdr_item

from .utils import dont_increase_depth, setup_profiling


class GeneralSpider(Spider):
    name = 'dd_crawler'

    def __init__(self, seeds=None, profile=None):
        super().__init__()
        self.le = LinkExtractor()
        if seeds:
            with open(seeds) as f:
                self.start_urls = [line.strip() for line in f]
        if profile:
            setup_profiling(profile)

    def parse(self, response):
        if not isinstance(response, HtmlResponse):
            return

        if self.settings.getbool('AUTOPAGER'):
            for url in autopager.urls(response):
                with dont_increase_depth(response):
                    yield Request(url=url)

        for link in self.le.extract_links(response):
            yield Request(url=link.url)

        yield self.page_item(response)

    def page_item(self, response):
        return text_cdr_item(
            response,
            crawler_name=self.settings.get('CDR_CRAWLER'),
            team_name=self.settings.get('CDR_TEAM'),
            metadata={
                'depth': response.meta.get('depth'),
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

    def parse(self, response):
        if not isinstance(response, HtmlResponse):
            return

        urls = self.clf.extract_urls(response.text, response.url)
        for score, url in urls:
            priority = int(
                score * self.settings.getfloat('DD_PRIORITY_MULTIPLIER'))
            yield Request(url, priority=priority)

        yield self.page_item(response)
