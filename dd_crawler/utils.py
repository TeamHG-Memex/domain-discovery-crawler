import re
import time
from urllib.parse import urlsplit


def warn_if_slower(limit, logger):
    def deco(fn):
        def inner(*args, **kwargs):
            t0 = time.time()
            try:
                return fn(*args, **kwargs)
            finally:
                took = time.time() - t0
                if took > limit:
                    logger.warning('Warning: {} took {:.3f} s'.format(
                        fn.__name__, took))
        return inner
    return deco


def get_domain(url):
    domain = urlsplit(url).netloc
    return re.sub(r'^www\.', '', domain)
