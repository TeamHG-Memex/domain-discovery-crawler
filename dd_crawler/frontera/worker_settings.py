from frontera.settings.default_settings import MIDDLEWARES

from .common_settings import *


SPIDER_LOG_PARTITIONS = 1
MAX_NEXT_REQUESTS = 512


BACKEND = 'frontera.contrib.backends.sqlalchemy.SQLAlchemyBackend'
# BACKEND = 'frontera.contrib.backends.sqlalchemy.Distributed'


SQLALCHEMYBACKEND_ENGINE = 'postgresql+psycopg2://ddc:ddc@frontera-db/frontera'
SQLALCHEMYBACKEND_ENGINE_ECHO = False
SQLALCHEMYBACKEND_DROP_ALL_TABLES = False
SQLALCHEMYBACKEND_CLEAR_CONTENT = False


MIDDLEWARES.extend([
    'frontera.contrib.middlewares.domain.DomainMiddleware',
    'frontera.contrib.middlewares.fingerprint.DomainFingerprintMiddleware'
])


LOGGING_CONFIG = 'logging.conf'


