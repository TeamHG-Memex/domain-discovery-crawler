import contextlib
import logging
import re
import os.path
import signal
import time
from urllib.parse import urlsplit

from deepdeep.utils import html2text
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
            x = html2text(html)
        elif self.classifier_input == 'text_url':
            x = {'text': html2text(html), 'url': url}
        else:
            raise RuntimeError
        return float(self.clf.predict_proba([x])[0][1])
