from scrapy.exceptions import IgnoreRequest
from scrapy.downloadermiddlewares.redirect import RedirectMiddleware

from ..utils import get_domain


class ForbidOffsiteRedirectsMiddleware(RedirectMiddleware):
    def __init__(self, settings):
        super().__init__(settings)
        self.domain_limit = settings.getbool('DOMAIN_LIMIT')

    def _redirect(self, redirected, request, spider, reason):
        if self.domain_limit and \
                get_domain(redirected.url) != get_domain(request.url):
            raise IgnoreRequest('Redirecting off-domain')
        return super()._redirect(redirected, request, spider, reason)
