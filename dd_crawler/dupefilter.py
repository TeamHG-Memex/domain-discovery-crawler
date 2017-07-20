import hashlib

from scrapy_redis.dupefilter import RFPDupeFilter
from scrapy.utils.python import to_bytes
from w3lib.url import canonicalize_url


class LoginAwareDupefilter(RFPDupeFilter):
    def request_seen(self, request):
        fp = self._request_fingerprint(request)
        added = self.server.sadd(self.key, fp)
        return not added

    def _request_fingerprint(self, request):
        fp = hashlib.sha1()
        fp.update(to_bytes(request.method))
        fp.update(to_bytes(canonicalize_url(request.url)))
        fp.update(request.body or b'')
        # FIXME - proper field name
        fp.update(to_bytes('login={}'.format(request.meta.get('logged-in'))))
        return fp.hexdigest()
