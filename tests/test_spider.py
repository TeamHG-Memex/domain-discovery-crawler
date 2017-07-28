from __future__ import absolute_import

import redis
from scrapy.crawler import CrawlerRunner
from scrapy.settings import Settings
from scrapy_redis.defaults import SCHEDULER_QUEUE_KEY, SCHEDULER_DUPEFILTER_KEY
from twisted.web.resource import Resource

import dd_crawler.settings
from dd_crawler.spiders import BaseSpider
from .mockserver import MockServer
from .utils import text_resource, get_path, inlineCallbacks


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
    print(redis_server.keys('*'))

    settings = Settings()
    settings.setmodule(dd_crawler.settings)
    settings['ITEM_PIPELINES']['tests.utils.CollectorPipeline'] = 100
    settings.update(extra_settings)
    runner = CrawlerRunner(settings)
    return runner.create_crawler(spider_cls)


class Site(Resource):
    def __init__(self):
        Resource.__init__(self)
        self.putChild(b'', text_resource(
            '<a href="/page">page</a> '
            '<a href="/another-page">another page</a> '
        )())
        self.putChild(b'page', text_resource(
            '<a href="/another-page">another page</a>')())
        self.putChild(b'another-page', text_resource(
            '<a href="/new-page">new page</a>')())
        self.putChild(b'new-page', text_resource(
            '<a href="/page">page</a>')())


@inlineCallbacks
def test_spider(tmpdir):
    crawler = make_crawler()
    with MockServer(Site) as s:
        seeds = tmpdir.join('seeds.txt')
        seeds.write(s.root_url)
        yield crawler.crawl(seeds=str(seeds))
    spider = crawler.spider
    assert len(spider.collected_items) == 4
    assert {get_path(item['url']) for item in spider.collected_items} == \
           {'/', '/page', '/another-page', '/new-page'}
