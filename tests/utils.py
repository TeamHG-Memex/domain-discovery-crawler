from six.moves.urllib.parse import urlsplit, urlunsplit

import pytest
import redis
from scrapy.crawler import CrawlerRunner
from scrapy.settings import Settings
from scrapy.utils.log import configure_logging
from scrapy.utils.python import to_bytes
from scrapy_redis.defaults import SCHEDULER_QUEUE_KEY, SCHEDULER_DUPEFILTER_KEY
from twisted.internet import defer
from twisted.web.resource import Resource

import dd_crawler.settings
from dd_crawler.spiders import BaseSpider


class CollectorPipeline:
    def process_item(self, item, spider):
        if not hasattr(spider, 'collected_items'):
            spider.collected_items = []
        spider.collected_items.append(item)
        return item


# make the module importable without running py.test (for mockserver)
try:
    inlineCallbacks = pytest.inlineCallbacks
except AttributeError:
    inlineCallbacks = defer.inlineCallbacks


configure_logging()


def text_resource(content):
    class Page(Resource):
        isLeaf = True
        def render_GET(self, request):
            request.setHeader(b'content-type', b'text/html')
            request.setHeader(b'charset', b'utf-8')
            return to_bytes(content, encoding='utf-8')
    return Page()


def find_item(path, items, key='url'):
    item, = [item for item in items if get_path(item[key]) == path]
    return item


def get_path(url):
    p = urlsplit(url)
    return urlunsplit(['', '', p.path or '/', p.query, p.fragment])


class ATestBaseSpider(BaseSpider):
    name = 'test_base_spider'  # to have a different queue prefix


def make_crawler(spider_cls=ATestBaseSpider, **extra_settings):
    # clean up queue before starting spider
    assert spider_cls.name.startswith('test_'), 'pass a special test spider'
    redis_server = redis.from_url('redis://localhost')
    name = spider_cls.name
    redis_server.delete(
        SCHEDULER_DUPEFILTER_KEY % {'spider': name},
        *redis_server.keys(
            SCHEDULER_QUEUE_KEY % {'spider': name} + '*'))

    settings = Settings()
    settings.setmodule(dd_crawler.settings)
    settings['ITEM_PIPELINES']['tests.utils.CollectorPipeline'] = 100
    settings.update(extra_settings)
    runner = CrawlerRunner(settings)
    return runner.create_crawler(spider_cls)
