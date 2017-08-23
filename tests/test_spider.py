import json
from urllib.parse import quote

import pytest
from sklearn.externals import joblib
from twisted.web.resource import Resource

from dd_crawler.spiders import DeepDeepSpider
from .mockserver import MockServer
from .utils import (
    text_resource, get_path, inlineCallbacks, make_crawler, ATestBaseSpider)


class Site(Resource):
    def __init__(self):
        Resource.__init__(self)
        self.putChild(b'', text_resource(
            '<a href="/page">page</a> '
            '<a href="/another-page">another page</a> '
            '<a href="/страница">страница</a> '
        ))
        self.putChild(b'page', text_resource(
            '<a href="/another-page">another page</a>'))
        self.putChild(b'another-page', text_resource(
            '<a href="/new-page">new page</a>'))
        self.putChild(b'new-page', text_resource('<a href="/page">page</a>'))
        self.putChild('страница'.encode('utf8'),
                      text_resource('просто страница'))


class ATestRelevancySpider(DeepDeepSpider):
    name = 'test_relevancy_spider'


@pytest.mark.parametrize(
    ['spider_cls'], [[ATestBaseSpider], [ATestRelevancySpider]])
@inlineCallbacks
def test_spider(tmpdir, spider_cls):
    log_path = tmpdir.join('log.jl')
    spider_kwargs = {}
    if spider_cls is ATestRelevancySpider:
        spider_kwargs.update(relevancy_models(tmpdir))
    crawler = make_crawler(spider_cls=spider_cls,
                           RESPONSE_LOG_FILE=str(log_path))
    with MockServer(Site) as s:
        seeds = tmpdir.join('seeds.txt')
        seeds.write(s.root_url)
        yield crawler.crawl(seeds=str(seeds), **spider_kwargs)
    spider = crawler.spider
    assert len(spider.collected_items) == 5
    assert {get_path(item['url']) for item in spider.collected_items} == \
           {'/', '/page', '/another-page', '/new-page', quote('/страница')}
    with log_path.open('rt') as f:
        items = [json.loads(line) for line in f]
        assert len(items) == len(spider.collected_items)


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
