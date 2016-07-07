BOT_NAME = 'dd_crawler'

SPIDER_MODULES = ['dd_crawler.spiders']
NEWSPIDER_MODULE = 'dd_crawler.spiders'

USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/51.0.2704.84 Safari/537.36')

# Scrapy-redis settings
# Enables scheduling storing requests queue in redis.
SCHEDULER = "scrapy_redis.scheduler.Scheduler"
# Don't cleanup redis queues, allows to pause/resume crawls.
SCHEDULER_PERSIST = True
# SCHEDULER_QUEUE_CLASS = 'dd_crawler.queue.CompactQueue'
SCHEDULER_QUEUE_CLASS = 'dd_crawler.queue.BatchSoftmaxQueue'
QUEUE_BATCH_SIZE = 500

COMMANDS_MODULE = 'dd_crawler.commands'

DOMAIN_LIMIT = False
RESET_DEPTH = False

DD_PRIORITY_MULTIPLIER = 10000
DD_BALANCING_TEMPERATURE = 0.1
DD_MAX_SCORE = 10 * DD_PRIORITY_MULTIPLIER

REDIRECT_PRIORITY_ADJUST = 10 * DD_PRIORITY_MULTIPLIER

DEPTH_PRIORITY = 1

DOWNLOADER_MIDDLEWARES = {
    'scrapy.downloadermiddlewares.redirect.RedirectMiddleware': None,
    'dd_crawler.middleware.domains.ForbidOffsiteRedirectsMiddleware': 600,
}

SPIDER_MIDDLEWARES = {
    'dd_crawler.middleware.domains.DomainControlMiddleware': 550,
}

HTTPCACHE_ENABLED = False
REDIRECT_ENABLED = True
COOKIES_ENABLED = True
DOWNLOAD_TIMEOUT = 240
RETRY_ENABLED = False
DOWNLOAD_MAXSIZE = 1*1024*1024

# Auto throttling
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_DEBUG = False
AUTOTHROTTLE_MAX_DELAY = 3.0
AUTOTHROTTLE_START_DELAY = 1.0
RANDOMIZE_DOWNLOAD_DELAY = False

# Concurrency
CONCURRENT_REQUESTS = 64
CONCURRENT_REQUESTS_PER_DOMAIN = 10
DOWNLOAD_DELAY = 0.0

REACTOR_THREADPOOL_MAXSIZE = 32
DNS_TIMEOUT = 180

LOG_LEVEL = 'INFO'
