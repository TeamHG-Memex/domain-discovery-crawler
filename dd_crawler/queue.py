import random
from urllib.parse import urlsplit
from zlib import crc32
from typing import Optional, List, Tuple, Union, Dict
import logging
from functools import lru_cache
import time

from deepdeep.utils import softmax
import numpy as np
from scrapy import Request
from scrapy_redis.queue import Base

from .utils import warn_if_slower

logger = logging.getLogger(__name__)


# Note about race conditions: there are several workers executing this code, but
# - Redis itself is single-threaded
# - Only one worker should be crawling given domain, unless workers enter/leave


class BaseRequestQueue(Base):
    """ Request queue where each domain has a separate queue,
    and each domain is crawled only by one worker to be polite.

    QUEUE_CACHE_TIME setting determines the time queues are cached for,
    when workers do not change (stale cache only leads to missing new domains
    for a while, so it's safe to set it to higher values).
    """
    def __init__(self, *args, slots_mock=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.len_key = '{}:len'.format(self.key)  # redis int
        self.queues_key = '{}:queues'.format(self.key)  # redis sorted set
        self.workers_key = '{}:workers'.format(self.key)  # redis set
        self.worker_id_key = '{}:worker-id'.format(self.key)  # redis int
        self.worker_id = self.server.incr(self.worker_id_key)
        self.alive_timeout = 10  # seconds
        self.im_alive()
        self.n_requests = 0
        self.stat_each = 1000  # requests
        self.slots_mock = slots_mock
        self.queue_cache_time = \
            self.spider.settings.getint('QUEUE_CACHE_TIME', 1)  # seconds

    def __len__(self):
        return int(self.server.get(self.len_key) or '0')

    def push(self, request: Request):
        data = self._encode_request(request)
        score = -request.priority
        queue_key = self.request_queue_key(request)
        added = self.server.zadd(queue_key, **{data: score})
        if added:
            self.server.incr(self.len_key)
        top = self.server.zrange(queue_key, 0, 0, withscores=True)
        if top:
            (_, queue_score), = top
        else:  # a race during domain re-balancing: do not care about score much
            logger.warning('Placing a possibly incorrect queue score')
            queue_score = score
        queue_added = self.server.zadd(
            self.queues_key, **{queue_key: queue_score})
        if queue_added:
            logger.debug('ADD queue {}'.format(queue_key))

    def pop(self, timeout=0) -> Request:
        self.n_requests += 1
        if self.n_requests % self.stat_each == 0:
            logger.info('Queue size: {}, domains: {}'.format(
                len(self), self.server.zcard(self.queues_key)))
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

    def get_queues(self, withscores=False) \
            -> Union[List[bytes], List[Tuple[bytes, float]]]:
        return self.server.zrange(self.queues_key, 0, -1, withscores=withscores)

    def get_workers(self) -> List[bytes]:
        return self.server.smembers(self.workers_key)

    @warn_if_slower(0.1, logger)
    def select_queue_key(self) -> Optional[bytes]:
        """ Select which queue (domain) to use next.
        """
        idx, n_idx = self.discover()
        time_step = time.time()
        if self.queue_cache_time:
            time_step = int(time_step / self.queue_cache_time)
        my_queues = self.get_my_queues(idx, n_idx, time_step)
        while my_queues:
            queue = self.select_best_queue(my_queues)
            if self.server.zcard(queue):
                return queue
            else:
                del my_queues[queue]
                self.remove_empty_queue(queue)

    Queues = Dict[bytes, float]

    def select_best_queue(self, queues: Queues) -> bytes:
        """ Select queue to crawl from, taking free slots into account.
        """
        available_queues = self.get_available_queues(queues)
        return random.choice(list(available_queues or queues))

    def get_available_queues(self, queues: Queues) -> Queues:
        """ Return all queues with free slots.
        """
        slots = (self.spider.crawler.engine.downloader.slots
                 if self.slots_mock is None else self.slots_mock)
        available_queues = {}
        for q, s in queues.items():
            domain = self.queue_key_domain(q)
            if domain not in slots or slots[domain].free_transfer_slots():
                available_queues[q] = s
        return available_queues

    @lru_cache(maxsize=1)
    def get_my_queues(self, idx: int, n_idx: int, time_step: int) -> Queues:
        """ Get queues belonging to this worker.
        Here we cache not only expensive redis call, but a list comprehension
        below too.
        time_step key makes the cache live self.queue_cache_time seconds.
        Stale cache means we are not seeing new domains, nothing more.
        """
        queues = self.get_queues(withscores=True)
        return {q: s for q, s in queues if crc32(q) % n_idx == idx}

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
        pipe.zrange(queue_key, 0, 1, withscores=True)\
            .zremrangebyrank(queue_key, 0, 0)
        results, count = pipe.execute()
        if results:
            self.server.decr(self.len_key)
            if len(results) == 2:
                _, queue_score = results[1]
                self.server.zadd(
                    self.queues_key, **{queue_key.decode('utf8'): queue_score})
            else:
                self.remove_empty_queue(queue_key)
            return self._decode_request(results[0][0])
        else:
            # queue was empty: remove it from queues set
            self.remove_empty_queue(queue_key)

    def remove_empty_queue(self, queue_key: bytes) -> None:
        # FIXME - maybe we should not remove empty queue keys? That can be racy
        removed = self.server.zrem(self.queues_key, queue_key)
        if removed:
            logger.debug('REM queue {}'.format(queue_key))

    def request_queue_key(self, request: Request) -> str:
        """ Key for request queue (based on it's domain).
        """
        domain = urlsplit(request.url).netloc
        return '{}:domain:{}'.format(self.key, domain)

    def queue_key_domain(self, queue_key: bytes) -> str:
        queue_key = queue_key.decode('utf8')
        prefix = '{}:domain:'.format(self.key)
        assert queue_key.startswith(prefix)
        return queue_key[len(prefix):]

    def get_stats(self):
        """ Return all queue stats.
        """
        queues = self.get_queues(withscores=True)
        return dict(
            len=len(self),
            n_domains=len(queues),
            queues=[
                (name.decode('utf8'), -score, self.server.zcard(name))
                for name, score in queues],
        )


class CompactQueue(BaseRequestQueue):
    """ A more compact request representation:
    preserve only url, depth and priority.
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


class SoftmaxQueue(CompactQueue):
    def select_best_queue(self, queues: BaseRequestQueue.Queues) -> bytes:
        """ Select queue taking weights into account.
        """
        temprature = (
            self.spider.settings.getfloat('DD_BALANCING_TEMPERATURE') *
            self.spider.settings.getfloat('DD_PRIORITY_MULTIPLIER'))
        available_queues = self.get_available_queues(queues) or queues
        keys = list(available_queues)
        weights = [-available_queues[q] for q in keys]
        p = softmax(weights, t=temprature)
        return np.random.choice(keys, p=p)
