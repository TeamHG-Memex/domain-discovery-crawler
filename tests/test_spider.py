from twisted.web.resource import Resource

from .mockserver import MockServer
from .utils import text_resource, get_path, inlineCallbacks, make_crawler


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
