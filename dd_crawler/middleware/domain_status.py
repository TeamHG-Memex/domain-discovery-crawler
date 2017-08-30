from collections import defaultdict

from dd_crawler.utils import get_domain

from dd_crawler.signals import domain_status_opened


class DomainStatusMiddleware:
    def __init__(self):
        self._by_spider = defaultdict(lambda: dict(
            in_flight=defaultdict(set),
            have_successes=set(),
            have_failures=set(),
        ))

    @classmethod
    def from_crawler(cls, crawler):
        if crawler.settings.getbool('DOMAIN_LIMIT'):
            return cls()

    def process_request(self, request, spider):
        if spider not in self._by_spider:
            spider.crawler.signals.send_catch_log_deferred(
                signal=domain_status_opened, status=self._by_spider[spider])
        domain = get_domain(request.url)
        self._by_spider[spider]['in_flight'][domain].add(request.url)

    def process_response(self, request, response, spider):
        self._got_response(request, spider, is_failure=False)
        return response

    def process_exception(self, request, exception, spider):
        self._got_response(request, spider, is_failure=True)

    def _got_response(self, request, spider, *, is_failure: bool):
        stats = self._by_spider[spider]
        domain = get_domain(request.url)
        in_flight = stats['in_flight'][domain]
        try:
            in_flight.remove(request.url)
        except KeyError:
            pass
        stats['have_failures' if is_failure else 'have_successes'].add(domain)
