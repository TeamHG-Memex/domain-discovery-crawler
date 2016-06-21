import random
from urllib.parse import urlsplit

from scrapy_redis.queue import Base


class RequestQueue(Base):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.len_key = '{}:len'.format(self.key)
        self.queues_key = '{}:queues'.format(self.key)

    def __len__(self):
        return int(self.server.get(self.len_key) or '0')

    def push(self, request):
        data = self._encode_request(request)
        pairs = {data: -request.priority}
        queue_key = self.request_queue_key(request)
        added = self.server.zadd(queue_key, **pairs)
        if added:
            self.server.incr(self.len_key)
        self.server.sadd(self.queues_key, queue_key)

    def pop(self, timeout=0):
        queue_key = self.select_queue_key()
        if queue_key:
            return self.pop_from_queue(queue_key)

    def select_queue_key(self):
        """ Select which queue (domain) to use next.
        """
        # TODO:
        # - pin domain to worker
        # - select based on priority and available slots
        queues = self.server.smembers(self.queues_key)
        if queues:
            return random.choice(list(queues))

    def pop_from_queue(self, queue_key):
        """ Pop value with highest priority from the given queue.
        """
        pipe = self.server.pipeline()
        pipe.multi()
        pipe.zrange(queue_key, 0, 0).zremrangebyrank(queue_key, 0, 0)
        results, count = pipe.execute()
        if results:
            self.server.decr(self.len_key)
            return self._decode_request(results[0])

    def request_queue_key(self, request):
        """ Key for request queue (based on it's domain).
        """
        domain = urlsplit(request.url).netloc
        return '{}:domain:{}'.format(self.key, domain)

    def get_stats(self):
        """ Return all queue stats.
        """
        queues = self.server.smembers(self.queues_key)
        return dict(
            len=len(self),
            n_domains=len(queues),
            queues={name: self.server.zcard(name) for name in queues},
        )
