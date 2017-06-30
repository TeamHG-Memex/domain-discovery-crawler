import contextlib
from functools import lru_cache
import logging
import re
import os.path
import signal
import time
from urllib.parse import urlsplit
from typing import Optional

import html_text
from scrapy.settings import Settings
from sklearn.externals import joblib
import vmprof


logger = logging.getLogger(__name__)


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


def cacheforawhile(method):
    """ Cache method for some time, so that it does not become a bottleneck.
    """
    max_cache_time = 30 * 60  # seconds
    run_time_multiplier = 20
    last_call_time = None
    initial_cache_time = 0.5  # seconds
    cache_time = initial_cache_time

    @lru_cache(maxsize=1)
    def cached_method(*args, **kwargs):
        nonlocal cache_time
        kwargs.pop('time_key')
        t0 = time.time()
        try:
            return method(*args, **kwargs)
        finally:
            run_time = time.time() - t0
            cache_time = min(max_cache_time, run_time * run_time_multiplier)
            if cache_time > initial_cache_time:
                logger.info('{} took {:.2f} s, new cache time is {:.1f} s'
                            .format(method.__name__, run_time, cache_time))

    def inner(self, *args, **kwargs):
        if self.skip_cache:
            return method(self, *args, **kwargs)
        nonlocal last_call_time
        t = time.time()
        if not last_call_time or (t - last_call_time > cache_time):
            last_call_time = t
        kwargs['time_key'] = last_call_time
        return cached_method(self, *args, **kwargs)

    return inner


def get_domain(url):
    domain = urlsplit(url).netloc
    return re.sub(r'^www\.', '', domain)


@contextlib.contextmanager
def dont_increase_depth(response):
    # XXX: a hack to keep the same depth for outgoing requests
    response.meta['depth'] -= 1
    try:
        yield
    finally:
        response.meta['depth'] += 1


def get_int_or_None(settings: Settings, key: str) -> Optional[int]:
    value = settings.get(key)
    if value is None or value == '':
        return None
    return int(value)


def setup_profiling(profile):
    file, filename = None, None

    def handler(*_):
        nonlocal file, filename
        if file:
            vmprof.disable()
            file.close()
            file = None
            logger.info('vmprof saved to {}'.format(filename))
        else:
            filename = _get_prof_filename(profile)
            file = open(filename, 'wb')
            logger.info('vmprof writing to {}'.format(filename))
            vmprof.enable(file.fileno(), period=0.01)

    signal.signal(signal.SIGUSR1, handler)


def _get_prof_filename(profile: str) -> str:
    i = 1
    while True:
        filename = '{}_{}.vmprof'.format(profile, i)
        if not os.path.exists(filename):
            return filename
        i += 1


class PageClassifier:
    def __init__(self, clf_filename, classifier_input):
        self.clf = joblib.load(clf_filename)
        if classifier_input not in {'text', 'text_url'}:
            raise ValueError(
                'Invalid classifier_input value: {}'.format(classifier_input))
        self.classifier_input = classifier_input

    def get_score(self, html: str, url: str) -> float:
        if self.classifier_input == 'text':
            x = html_text.extract_text(html)
        elif self.classifier_input == 'text_url':
            x = {'text': html_text.extract_text(html), 'url': url}
        else:
            raise RuntimeError
        return float(self.clf.predict_proba([x])[0][1])
