import os
import time
from typing import List
from urllib.parse import urlsplit

import pytest
from redis.client import StrictRedis
from scrapy import Request, Spider
from scrapy.crawler import Crawler
from scrapy.utils.log import configure_logging
from scrapy_redis.defaults import SCHEDULER_QUEUE_KEY

from dd_crawler.spiders import _url_hash
from dd_crawler.queue import BaseRequestQueue, SoftmaxQueue, BatchQueue, \
    BatchSoftmaxQueue, url_compress, url_decompress


REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost')


class ATestSpider(Spider):
    name = 'test_dd_spider'


@pytest.fixture
def server():
    redis_server = StrictRedis.from_url(REDIS_URL)
    keys = redis_server.keys(
        SCHEDULER_QUEUE_KEY % {'spider': ATestSpider.name} + '*')
    if keys:
        redis_server.delete(*keys)
    return redis_server


@pytest.fixture(params=[
    BaseRequestQueue, SoftmaxQueue, BatchQueue, BatchSoftmaxQueue])
def queue_cls(request):
    return request.param


logging_configured = False


def make_queue(redis_server, cls: type, slots=None, skip_cache=True, settings=None,
               hints=None) -> BaseRequestQueue:
    global logging_configured
    if not logging_configured:
        configure_logging(settings=settings)
        logging_configured = True
    crawler = Crawler(Spider, settings=settings)
    if slots is None:
        slots = {}
    spider = Spider.from_crawler(crawler, 'test_dd_spider')
    if hints:
        spider.hint_urls = hints
    return cls(server=redis_server, spider=spider, key=SCHEDULER_QUEUE_KEY,
               slots_mock=slots, skip_cache=skip_cache)


def test_queue_key(server):
    q = make_queue(server, BaseRequestQueue)
    assert q.url_queue_key('http://wwww.example.com/foo') == \
        'test_dd_spider:requests:domain:example.com'
    assert q.url_queue_key('https://example2.com/foo') == \
        'test_dd_spider:requests:domain:example2.com'
    assert q.url_queue_key('http://app.example.co.uk') == \
        'test_dd_spider:requests:domain:example.co.uk'


def test_push_pop(server, queue_cls):
    q = make_queue(server, queue_cls)
    assert q.pop() is None
    assert len(q) == 0
    assert q.get_queues() == []
    r1 = Request('http://example.com', priority=100, meta={'depth': 10})
    q.push(r1)
    assert len(q) == 1
    assert q.get_queues() == [b'test_dd_spider:requests:domain:example.com']
    assert q.select_queue_key() == b'test_dd_spider:requests:domain:example.com'
    r1_ = q.pop()
    assert r1_.url == r1.url
    assert r1_.priority == r1.priority
    assert r1_.meta['depth'] == r1.meta['depth']
    assert len(q) == 0
    assert q.pop() is None


def test_max_domains(server, queue_cls):
    q = make_queue(server, queue_cls, settings={'QUEUE_MAX_DOMAINS': 2})
    q.push(Request('http://domain-1.com'))
    q.push(Request('http://domain-2.com'))
    q.push(Request('http://domain-2.com/foo'))
    q.push(Request('http://domain-3.com/foo'))
    q.push(Request('http://domain-1.com/foo'))
    urls = set()
    while True:
        r = q.pop()
        if r is None:
            break
        urls.add(r.url)
    assert urls == {'http://domain-1.com', 'http://domain-2.com',
                    'http://domain-2.com/foo', 'http://domain-1.com/foo'}


def test_max_relevant_domains(server, queue_cls):
    q = make_queue(server, queue_cls,
                   settings={'QUEUE_MAX_RELEVANT_DOMAINS': 2, 'RESTRICT_DELAY': 1})
    assert q.push(Request('http://domain-1.com'))
    q.page_is_relevant('http://domain-1.com', 1.1)
    assert q.push(Request('http://domain-2.com'))
    q.page_is_relevant('http://domain-2.com', 0.8)
    assert q.push(Request('http://domain-3.com/foo'))
    q.page_is_relevant('http://domain-3.com/foo', 1)
    assert q.push(Request('http://domain-2.com/foo'))
    q.page_is_relevant('http://domain-2.com/foo', 0.8)
    assert q.push(Request('http://domain-1.com/foo'))
    q.try_to_restrict_domains()  # too early
    assert not q.did_restrict_domains
    # did not pop yet, so can push a new domain
    assert q.push(Request('http://domain-4.com/foo'))
    time.sleep(1)
    urls = set()
    while True:
        r = q.pop()
        assert q.did_restrict_domains
        if r is None:
            break
        urls.add(r.url)
    assert urls == {'http://domain-1.com', 'http://domain-2.com',
                    'http://domain-2.com/foo', 'http://domain-1.com/foo'}
    # now relevant domains have been selected, can not push
    assert not q.push(Request('http://domain-5.com/foo'))
    assert not q.pop()


def test_priority(server, queue_cls):
    q = make_queue(server, queue_cls)
    q.push(Request('http://example.com/1', priority=10))
    q.push(Request('http://example.com/2', priority=100))
    q.push(Request('http://example.com/3', priority=1))
    assert [q.pop().url for _ in range(3)] == [
        'http://example.com/2',
        'http://example.com/1',
        'http://example.com/3']
    assert q.pop() is None


def test_domain_distribution(server, queue_cls):
    q1 = make_queue(server, queue_cls)
    q2 = make_queue(server, queue_cls)
    urls = ['http://a.com', 'http://a.com/foo', 'http://b.com',
            'http://b.com/foo', 'http://tado8.com', 'http://tada.com',
            'http://tada.com/asdfsd']
    for url in urls:
        q1.push(Request(url=url))  # queue does not matter
    urls1 = {
        'http://a.com', 'http://a.com/foo', 'http://b.com', 'http://b.com/foo'}
    urls2 = {'http://tado8.com', 'http://tada.com', 'http://tada.com/asdfsd'}
    reqs1 = pop_all(q1)
    assert {r.url for r in reqs1} == urls1
    assert len(q1) == len(q2) == len(urls2)
    reqs2 = pop_all(q2)
    assert {r.url for r in reqs2} == urls2


def test_batch_softmax_queue_simple(server):
    q = make_queue(server, BatchSoftmaxQueue, settings={'QUEUE_BATCH_SIZE': 50})
    for domain_n in range(10):
        for url_n in range(10):
            q.push(Request(
                url='http://domain-{}.com/{}'.format(domain_n, url_n),
                priority=domain_n * url_n,
            ))
    res = q.pop_multi()
    assert len(res) == 50
    assert len({urlsplit(r.url).netloc for r in res}) == 10


def test_batch_softmax_queue_one_domain(server):
    q = make_queue(server, BatchSoftmaxQueue, settings={'QUEUE_BATCH_SIZE': 50})
    for url_n in range(100):
        q.push(Request(
            url='http://domain.com/{}'.format(url_n),
            priority=url_n,
        ))
    res = q.pop_multi()
    assert len(res) == 50
    assert len({r.url for r in res}) == 50


def test_batch_softmax_enough_queues(server):
    q = make_queue(server, BatchSoftmaxQueue, settings={'QUEUE_BATCH_SIZE': 50})
    for domain_n in range(100):
        for url_n in range(10):
            q.push(Request(
                url='http://domain-{}.com/{}'.format(domain_n, url_n),
                priority=domain_n * url_n,
            ))
    res = q.pop_multi()
    assert len(res) == 50
    assert len({r.url for r in res}) == 50
    assert len({urlsplit(r.url).netloc for r in res}) > 30


def test_batch_softmax_high_prob(server, priority=10000):
    q = make_queue(server, BatchSoftmaxQueue, settings={'QUEUE_BATCH_SIZE': 50})
    for domain_n in range(100):
        for url_n in range(5):
            q.push(Request(
                url='http://domain-{}.com/{}'.format(domain_n, url_n),
                priority=priority
                if (domain_n in [42, 43] and url_n == 1) else 0,
            ))
    res = q.pop_multi()
    urls = {r.url for r in res}
    assert 'http://domain-42.com/1' in urls
    assert 'http://domain-43.com/1' in urls
    assert len({urlsplit(r.url).netloc for r in res}) > 10
    assert len(res) == 50


# FIXME - broken in ebd4cb651050fcdae5427383f3d07b094f853155
# TODO - add a test for the infinite loop fixed in ^^
@pytest.mark.skip
def test_batch_softmax_degenerate_prob(server):
    test_batch_softmax_high_prob(server, priority=100000000)


def test_url_compress():
    for url in ['http://www.example.com/?foo=%20+',
                'https://example.ru/~ONLY-ASCII-ALLOWED-HERE']:
        assert url == url_decompress(url_compress(url))


def test_encode_request(server, queue_cls):
    q = make_queue(server, queue_cls)
    r = Request(
        'http://example.com/foo',
        meta={
            'depth': 123,
            'parent': _url_hash('http://example.com', as_bytes=True),
        })
    r2 = q._decode_request(q._encode_request(r))
    assert r.url == r2.url
    assert r.meta['depth'] == r2.meta['depth']
    assert r.meta['parent'] == r2.meta['parent']

    r = Request('http://example.com/foo', meta={'depth': 2**16})
    r2 = q._decode_request(q._encode_request(r))
    assert r2.meta['depth'] >= 2**15 - 1

    r = Request('http://example.com/foo', meta={'depth': -2**16})
    r2 = q._decode_request(q._encode_request(r))
    assert r2.meta['depth'] <= -2**15


def pop_all(q: BaseRequestQueue) -> List[Request]:
    requests = []
    while True:
        r = q.pop()
        if r is None:
            return requests
        requests.append(r)
