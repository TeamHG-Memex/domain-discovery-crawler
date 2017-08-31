from collections import defaultdict
import time

from scrapy.exceptions import NotConfigured

from dd_crawler.queue import BaseRequestQueue
from dd_crawler.signals import queues_changed
from dd_crawler.utils import get_domain
from .log import get_jl_logger


class DomainStatusMiddleware:
    def __init__(self, jl_logger):
        self._jl_logger = jl_logger
        self._in_flight = defaultdict(set)
        self._have_successes = set()
        self._have_failures = set()
        self._open_queues = []

    @classmethod
    def from_crawler(cls, crawler):
        if crawler.settings.getbool('DOMAIN_LIMIT'):
            log_path = crawler.settings.get('RESPONSE_LOG_FILE')
            if not log_path:
                raise NotConfigured('RESPONSE_LOG_FILE not defined')
            mw = cls(get_jl_logger(log_path))
            crawler.signals.connect(mw.on_queues_changed, queues_changed)
            return mw

    def process_request(self, request, spider):
        domain = get_domain(request.url)
        in_flight = self._in_flight[domain]
        if not in_flight:
            self._log_new_entry()
        in_flight.add(request.url)

    def process_response(self, request, response, spider):
        self._got_response(request, spider, is_failure=False)
        return response

    def process_exception(self, request, exception, spider):
        self._got_response(request, spider, is_failure=True)

    def _got_response(self, request, spider, *, is_failure: bool):
        domain = get_domain(request.url)
        in_flight = self._in_flight[domain]
        changed = False
        try:
            in_flight.remove(request.url)
        except KeyError:
            pass
        else:
            changed = len(in_flight) == 0
        s = self._have_failures if is_failure else self._have_successes
        changed = changed or (domain not in s)
        s.add(domain)
        if changed:
            self._log_new_entry()

    def on_queues_changed(self, queue: BaseRequestQueue):
        self._open_queues = [
            queue.queue_key_domain(q) for q in queue.get_queues()]

    def _log_new_entry(self):
        entry = {
            'time': time.time(),
            'domain_state': {
                'global_open_queues': sorted(self._open_queues),
                'worker_in_flight': sorted(
                    d for d, rs in self._in_flight.items() if rs),
                'worker_failures': sorted(self._have_failures),
                'worker_successes': sorted(self._have_successes),
            }
        }
        self._jl_logger.write_entry(entry)
