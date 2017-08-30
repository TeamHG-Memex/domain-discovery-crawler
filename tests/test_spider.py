import json
from urllib.parse import quote

import pytest
from sklearn.externals import joblib
from twisted.web.resource import Resource
from twisted.web.util import redirectTo

from dd_crawler.spiders import DeepDeepSpider
from .mockserver import MockServer
from .utils import (
    text_resource, get_path, inlineCallbacks, make_crawler, ATestBaseSpider,
    find_item,
)


class Site(Resource):
    def __init__(self):
        Resource.__init__(self)
        self.putChild(b'', text_resource(
            '<a href="/page">page</a> '
            '<a href="/another-page">another page</a> '
            '<a href="/страница">страница</a> '
        ))

        class RedirectToLast(Resource):
            isLeaf = True
            def render_GET(self, request):
                return redirectTo(b'last', request)

        self.putChild(b'page', text_resource(
            '<a href="/another-page">another page</a>'))
        self.putChild(b'another-page', text_resource(
            '<a href="/new-page">new page</a>'))
        self.putChild(b'new-page', text_resource('<a href="/page">page</a>'))
        self.putChild('страница'.encode('utf8'),
                      text_resource('<a href="/redirect">ещё страница</a>'))
        self.putChild(b'redirect', RedirectToLast())
        self.putChild(b'last', text_resource('fin'))


class ATestRelevancySpider(DeepDeepSpider):
    name = 'test_relevancy_spider'


@pytest.mark.parametrize(
    ['spider_cls', 'domain_limit'],
    [[ATestBaseSpider, True],
     [ATestBaseSpider, False],
     [ATestRelevancySpider, False],
     ])
@inlineCallbacks
def test_spider(tmpdir, spider_cls, domain_limit):
    log_path = tmpdir.join('log.jl')
    spider_kwargs = {}
    if spider_cls is ATestRelevancySpider:
        spider_kwargs.update(relevancy_models(tmpdir))
    crawler = make_crawler(spider_cls=spider_cls,
                           RESPONSE_LOG_FILE=str(log_path),
                           DOMAIN_LIMIT=int(domain_limit))
    with MockServer(Site) as s:
        seeds = tmpdir.join('seeds.txt')
        seeds.write('\n'.join([s.root_url, 'http://not-localhost']))
        yield crawler.crawl(seeds=str(seeds), **spider_kwargs)
    spider = crawler.spider

    # check collected items
    assert len(spider.collected_items) == 6
    assert {get_path(item['url']) for item in spider.collected_items} == \
           {'/', '/page', '/another-page', '/new-page', quote('/страница'),
            '/last'}

    # check json lines log
    with log_path.open('rt') as f:
        items = [json.loads(line) for line in f]
        assert len(items) == len(spider.collected_items)

    # check parent/child relations
    find_meta = lambda path: find_item(path, spider.collected_items)['metadata']
    assert find_meta('/page')['parent'] == find_meta('/')['id']
    assert find_meta('/new-page')['parent'] != find_meta('/')['id']
    assert find_meta(quote('/страница'))['parent'] == find_meta('/')['id']
    assert find_meta('/last')['parent'] == find_meta(quote('/страница'))['id']

    if domain_limit:
        states = [item['domain_state'] for item in items
                  if 'domain_state' in item]
        s0, s1 = states
        assert s0['localhost'] == 'running'
        assert s0['not-localhost'] in {'running', 'failed'}
        assert s1 == {'localhost': 'finished', 'not-localhost': 'failed'}


class PageClf:
    def predict_proba(self, x):
        return [[0.5, 0.5]] * len(x)


class LinkVectorizer:
    def transform(self, links):
        return links


class QModel:
    def join_As(self, x, y):
        return x

    def predict(self, x):
        return [0.5] * len(x)


def relevancy_models(tmpdir):
    page_clf_path = tmpdir.join('page_clf.joblib')
    with page_clf_path.open('wb') as f:
        joblib.dump(PageClf(), f)
    link_clf_path = tmpdir.join('link_clf.joblib')
    with link_clf_path.open('wb') as f:
        joblib.dump({
            'Q': QModel(),
            'link_vectorizer': LinkVectorizer(),
            'page_vectorizer': None,
        }, f)
    return {
        'clf': link_clf_path,
        'page_clf': str(page_clf_path),
    }
