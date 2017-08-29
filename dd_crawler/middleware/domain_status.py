from collections import defaultdict

from dd_crawler.utils import get_domain


# TODO - pass this values to RequestLogMiddleware somehow. via spider?


class DomainStatusMiddleware:
    def __init__(self):
        self._in_flight = defaultdict(set)
        self._have_successes = set()
        self._have_failures = set()

    @classmethod
    def from_crawler(cls, crawler):
        if crawler.settings.getbool('DOMAIN_LIMIT'):
            return cls()

    def process_request(self, request, spider):
        key = self._key(request, spider)
        self._in_flight[key].add(request.url)

    def process_response(self, request, response, spider):
        key = self._key(request, spider)
        self._in_flight[key].pop(key, None)
        self._have_successes.add(key)
        return response

    def process_exception(self, request, exception, spider):
        key = self._key(request, spider)
        self._in_flight[key].pop(key, None)
        self._have_failures.add(key)

    def _key(self, request, spider):
        return spider, get_domain(request.url)
