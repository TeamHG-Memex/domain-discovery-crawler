from contextlib import contextmanager
import logging

from scrapy import Request
from scrapy.exceptions import IgnoreRequest
from scrapy.downloadermiddlewares.redirect import RedirectMiddleware

from ..utils import get_domain


logger = logging.getLogger(__name__)


class GetDomainLimitFromSpider:
    def __init__(self, domain_limit):
        self._domain_limit = domain_limit

    def domain_limit(self, spider):
        return getattr(spider, 'domain_limit', self._domain_limit)


class ForbidOffsiteRedirectsMiddleware(
        RedirectMiddleware, GetDomainLimitFromSpider):
    """ Forbid doing off-domain redirects when domain limit is True.

    Usage:

    Set domain_limit on spider instance, or DOMAIN_LIMIT in settings
    DOWNLOADER_MIDDLEWARES = {
        'scrapy.downloadermiddlewares.redirect.RedirectMiddleware': None,
        'dd_crawler.middleware.domains.ForbidOffsiteRedirectsMiddleware': 600,
    }
    """
    def __init__(self, settings):
        super().__init__(settings)
        GetDomainLimitFromSpider.__init__(self, settings.getbool('DOMAIN_LIMIT'))

    def _redirect(self, redirected, request, spider, reason):
        if self.domain_limit(spider) and \
                get_domain(redirected.url) != get_domain(request.url):
            raise IgnoreRequest('Redirecting off-domain')
        return super()._redirect(redirected, request, spider, reason)


class DomainControlMiddleware(GetDomainLimitFromSpider):
    """ Control domains when making requests:
    - do not make off-domain requests when domain limit is True
    - reset depth for off-domain requests when RESET_DEPTH is True

    Usage:

    Set domain_limit on spider instance, or DOMAIN_LIMIT in settings
    RESET_DEPTH = True or False
    SPIDER_MIDDLEWARES = {
        'dd_crawler.middleware.domains.DomainControlMiddleware': 550,
    }
    """
    def __init__(self, *, domain_limit, reset_depth):
        super().__init__(domain_limit)
        self.reset_depth = reset_depth

    @classmethod
    def from_crawler(cls, crawler):
        s = crawler.settings
        return cls(
            domain_limit=crawler.settings.getbool('DOMAIN_LIMIT'),
            reset_depth=s.getbool('RESET_DEPTH'))

    def process_spider_output(self, response, result, spider):
        domain = get_domain(response.request.url)
        for item in (result or []):
            if not isinstance(item, Request):
                yield item
            else:
                different_domain = get_domain(item.url) != domain
                if self.domain_limit(spider) and different_domain:
                    logger.debug('Dropping off-domain request {}'.format(item))
                else:
                    with _reset_depth_if(
                            self.reset_depth and different_domain, response):
                        yield item


@contextmanager
def _reset_depth_if(reset, response):
    depth = response.meta.get('depth')
    if reset:
        response.meta['depth'] = 0
    try:
        yield
    finally:
        if reset:
            response.meta['depth'] = depth
