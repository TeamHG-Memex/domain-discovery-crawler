from datetime import timedelta

from frontera.settings.default_settings import MIDDLEWARES


SPIDER_FEED_PARTITIONS = 2
SPIDER_LOG_PARTITIONS = 1
MAX_NEXT_REQUESTS = 512


BACKEND = 'frontera.contrib.backends.sqlalchemy.Distributed'


SQLALCHEMYBACKEND_ENGINE = 'sqlite:///url_storage.sqlite'
SQLALCHEMYBACKEND_ENGINE_ECHO = False
SQLALCHEMYBACKEND_DROP_ALL_TABLES = False
SQLALCHEMYBACKEND_CLEAR_CONTENT = False
# SQLALCHEMYBACKEND_REVISIT_INTERVAL = timedelta(days=3)


MIDDLEWARES.extend([
    'frontera.contrib.middlewares.domain.DomainMiddleware',
    'frontera.contrib.middlewares.fingerprint.DomainFingerprintMiddleware'
])


LOGGING_CONFIG = 'logging.conf'


