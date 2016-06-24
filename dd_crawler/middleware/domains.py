from contextlib import contextmanager
import logging

from scrapy import Request
from scrapy.exceptions import IgnoreRequest
from scrapy.downloadermiddlewares.redirect import RedirectMiddleware

from ..utils import get_domain


logger = logging.getLogger(__name__)


class ForbidOffsiteRedirectsMiddleware(RedirectMiddleware):
    """ Forbid doing off-domain redirects when DOMAIN_LIMIT is True.

    Usage:

    DOMAIN_LIMIT = True
    DOWNLOADER_MIDDLEWARES = {
        'scrapy.downloadermiddlewares.redirect.RedirectMiddleware': None,
        'dd_crawler.middleware.domains.ForbidOffsiteRedirectsMiddleware': 600,
    }
    """
    def __init__(self, settings):
        super().__init__(settings)
        self.domain_limit = settings.getbool('DOMAIN_LIMIT')

    def _redirect(self, redirected, request, spider, reason):
        if self.domain_limit and \
                get_domain(redirected.url) != get_domain(request.url):
            raise IgnoreRequest('Redirecting off-domain')
        return super()._redirect(redirected, request, spider, reason)


class DomainControlMiddleware:
    """ Control domains when making requests:
    - do not make off-domain requests when DOMAIN_LIMIT is True
    - reset depth for off-domain requests when RESET_DEPTH is True

    Usage:

    DOMAIN_LIMIT = True or False
    RESET_DEPTH = True or False
    SPIDER_MIDDLEWARES = {
        'dd_crawler.middleware.domains.DomainControlMiddleware': 550,
    }
    """
    def __init__(self, *, domain_limit, reset_depth):
        self.domain_limit = domain_limit
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
                if self.domain_limit and different_domain:
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
