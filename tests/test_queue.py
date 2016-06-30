import os

import pytest
import redis
from scrapy import Request, Spider
from scrapy.crawler import Crawler
from scrapy_redis.scheduler import QUEUE_KEY

from dd_crawler.queue import BaseRequestQueue, SoftmaxQueue


# allow test settings from environment
# TODO - use a custom testing db?
REDIS_URL = os.environ.get('REDIST_URL', 'redis://localhost')


class ATestSpider(Spider):
    name = 'test_dd_spider'


@pytest.fixture
def server():
    redis_server = redis.from_url(REDIS_URL)
    keys = redis_server.keys(QUEUE_KEY % {'spider': ATestSpider.name} + '*')
    if keys:
        redis_server.delete(*keys)
    return redis_server


@pytest.fixture(params=[BaseRequestQueue, SoftmaxQueue, SoftmaxQueue])
def queue_cls(request):
    return request.param


def make_queue(redis_server, cls, slots=None, skip_cache=True):
    crawler = Crawler(Spider)
    if slots is None:
        slots = {}
    spider = Spider.from_crawler(crawler, 'test_dd_spider')
    return cls(server=redis_server, spider=spider, key=QUEUE_KEY,
               slots_mock=slots, skip_cache=skip_cache)


def test_push_pop(server, queue_cls):
    q = make_queue(server, queue_cls)
    assert q.pop() is None
    assert q.get_queues() == []
    r1 = Request('http://example.com', priority=100, meta={'depth': 10})
    q.push(r1)
    assert q.get_queues() == [b'test_dd_spider:requests:domain:example.com']
    assert q.select_queue_key() == b'test_dd_spider:requests:domain:example.com'
    r1_ = q.pop()
    assert r1_.url == r1.url
    assert r1_.priority == r1.priority
    assert r1_.meta['depth'] == r1.meta['depth']
    assert q.pop() is None


def test_priority(server, queue_cls):
    q = make_queue(server, queue_cls)
    q.push(Request('http://example.com/1', priority=10))
    q.push(Request('http://example.com/2', priority=100))
    q.push(Request('http://example.com/3', priority=1))
    assert [q.pop().url for _ in range(3)] == [
        'http://example.com/2',
        'http://example.com/1',
        'http://example.com/3']


def test_domain_distribution(server, queue_cls):
    q1 = make_queue(server, queue_cls)
    q2 = make_queue(server, queue_cls)
    for url in ['http://a.com', 'http://a.com/foo', 'http://b.com',
                'http://b.com/foo', 'http://c.com']:
        q1.push(Request(url=url))  # queue does not matter
    # TODO