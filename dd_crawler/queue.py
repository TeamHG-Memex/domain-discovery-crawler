import random
from urllib.parse import urlsplit
from zlib import crc32
from typing import Optional, List, Tuple
import logging
from functools import lru_cache
import time

from scrapy import Request
from scrapy_redis.queue import Base

from .utils import warn_if_slower


logger = logging.getLogger(__name__)


# Note about race conditions: there are several workers executing this code, but
# - Redis itself is single-threaded
# - Only one worker should be crawling given domain, unless workers enter/leave


class RequestQueue(Base):
    """ Request queue where each domain has a separate queue,
    and each domain is crawled only by one worker to be polite.

    QUEUE_CACHE_TIME setting determines the time queues are cached for,
    when workers do not change (stale cache only leads to missing new domains
    for a while, so it's safe to set it to higher values).
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.len_key = '{}:len'.format(self.key)
        self.queues_key = '{}:queues'.format(self.key)
        self.workers_key = '{}:workers'.format(self.key)
        self.worker_id_key = '{}:worker-id'.format(self.key)
        self.worker_id = self.server.incr(self.worker_id_key)
        self.alive_timeout = 10  # seconds
        self.im_alive()
        self.n_requests = 0
        self.stat_each = 1000  # requests
        self.queue_cache_time = \
            self.spider.settings.getint('QUEUE_CACHE_TIME', 1)  # seconds

    def __len__(self):
        return int(self.server.get(self.len_key) or '0')

    def push(self, request: Request):
        data = self._encode_request(request)
        pairs = {data: -request.priority}
        queue_key = self.request_queue_key(request)
        added = self.server.zadd(queue_key, **pairs)
        if added:
            self.server.incr(self.len_key)
        queue_added = self.server.sadd(self.queues_key, queue_key)
        if queue_added:
            logger.debug('ADD queue {}'.format(queue_key))

    def pop(self, timeout=0) -> Request:
        self.n_requests += 1
        if self.n_requests % self.stat_each == 0:
            logger.info('Queue size: {}, domains: {}'.format(
                len(self), self.server.scard(self.queues_key)))
        queue_key = self.select_queue_key()
        if queue_key:
            return self.pop_from_queue(queue_key)

    def clear(self):
        keys = {
            self.len_key, self.queues_key, self.workers_key, self.worker_id_key}
        keys.update(self.get_workers())
        keys.update(self.get_queues())
        self.server.delete(*keys)
        super().clear()

    def get_queues(self) -> List[bytes]:
        return self.server.smembers(self.queues_key)

    def get_workers(self) -> List[bytes]:
        return self.server.smembers(self.workers_key)

    @warn_if_slower(0.1, logger)
    def select_queue_key(self) -> Optional[bytes]:
        """ Select which queue (domain) to use next.
        """
        idx, n_idx = self.discover()
        time_step = int(time.time() / self.queue_cache_time)
        my_queues = self.get_my_queues(idx, n_idx, time_step)
        while my_queues:
            # TODO: select based on priority and available slots
            queue = random.choice(my_queues)
            if self.server.zcard(queue):
                return queue
            else:
                my_queues.remove(queue)
                self.remove_empty_queue(queue)

    @lru_cache(maxsize=1)
    def get_my_queues(self, idx: int, n_idx: int, time_step: int)\
            -> List[bytes]:
        """ Get queues belonging to this worker.
        Here we cache not only expensive redis call, but a list comprehension
        below too.
        time_step key makes the cache live self.queue_cache_time seconds.
        Stale cache means we are not seeing new domains, nothing more.
        """
        queues = self.get_queues()
        return [q for q in queues if crc32(q) % n_idx == idx]

    def discover(self) -> Tuple[int, int]:
        """ Return a tuple of (my index, total number of workers).
        When workers connect or disconnect, this will cause re-distribution
        of domains between workers, but this is not an issue.
        """
        self.im_alive()
        worker_ids = set(map(int, self.get_workers()))
        for worker_id in list(worker_ids):
            if not self.is_alive(worker_id):
                self.server.srem(self.workers_key, worker_id)
                worker_ids.remove(worker_id)
        if self.worker_id in worker_ids:
            worker_ids = sorted(worker_ids)
            return worker_ids.index(self.worker_id), len(worker_ids)
        else:
            # This should not happen normally
            logger.warning('No live workers: selecting self!')
            return 0, 1

    def im_alive(self):
        """ Tell the server that current worker is alive.
        """
        pipe = self.server.pipeline()
        pipe.multi()
        pipe.sadd(self.workers_key, self.worker_id)\
            .set(self._worker_key(self.worker_id), 'ok', ex=self.alive_timeout)\
            .execute()

    def is_alive(self, worker_id) -> bool:
        """ Return whether given worker is alive.
        """
        return bool(self.server.get(self._worker_key(worker_id)))

    def _worker_key(self, worker_id) -> str:
        return '{}:worker-{}'.format(self.key, worker_id)

    def pop_from_queue(self, queue_key: bytes) -> Request:
        """ Pop value with highest priority from the given queue.
        """
        pipe = self.server.pipeline()
        pipe.multi()
        pipe.zrange(queue_key, 0, 0).zremrangebyrank(queue_key, 0, 0)
        results, count = pipe.execute()
        if results:
            self.server.decr(self.len_key)
            return self._decode_request(results[0])
        else:
            # queue was empty: remove it from queues set
            self.remove_empty_queue(queue_key)

    def remove_empty_queue(self, queue_key: bytes) -> None:
        removed = self.server.srem(self.queues_key, queue_key)
        if removed:
            logger.debug('REM queue {}'.format(queue_key))

    def request_queue_key(self, request: Request) -> str:
        """ Key for request queue (based on it's domain).
        """
        domain = urlsplit(request.url).netloc
        return '{}:domain:{}'.format(self.key, domain)

    def get_stats(self):
        """ Return all queue stats.
        """
        queues = self.get_queues()
        return dict(
            len=len(self),
            n_domains=len(queues),
            queues={name: self.server.zcard(name) for name in queues},
        )


class CompactRequestQueue(RequestQueue):
    """ Queue with a more compact request representation:
    in our case, we need to preserve only url and priority.
    """
    def _encode_request(self, request: Request) -> str:
        return '{} {} {}'.format(
            int(request.priority),
            request.meta.get('depth', 0),
            request.url)

    def _decode_request(self, encoded_request: bytes) -> Request:
        priority, depth, url = encoded_request.decode('utf-8').split(' ', 2)
        return Request(
            url, priority=int(priority), meta={'depth': int(depth)})
