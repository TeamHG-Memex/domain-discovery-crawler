BOT_NAME = 'dd_crawler'

SPIDER_MODULES = ['dd_crawler.spiders']
NEWSPIDER_MODULE = 'dd_crawler.spiders'

#USER_AGENT = 'topic (+http://www.yourdomain.com)'

FRONTERA_SETTINGS = 'dd_crawler.frontera.spider_settings'

SPIDER_MIDDLEWARES = {
    'frontera.contrib.scrapy.middlewares.schedulers.SchedulerSpiderMiddleware': 1000,
    'scrapy.spidermiddleware.depth.DepthMiddleware': None,
    'scrapy.spidermiddleware.offsite.OffsiteMiddleware': None,
    'scrapy.spidermiddleware.referer.RefererMiddleware': None,
    'scrapy.spidermiddleware.urllength.UrlLengthMiddleware': None
}

DOWNLOADER_MIDDLEWARES = {
    'frontera.contrib.scrapy.middlewares.schedulers.SchedulerDownloaderMiddleware': 1000,
}

SCHEDULER = 'frontera.contrib.scrapy.schedulers.frontier.FronteraScheduler'
# TODO - move to a different approach of seed loading
SPIDER_MIDDLEWARES.update({
    'frontera.contrib.scrapy.middlewares.seeds.file.FileSeedLoader': 1,
})


HTTPCACHE_ENABLED = False
REDIRECT_ENABLED = True
COOKIES_ENABLED = True
DOWNLOAD_TIMEOUT = 240
RETRY_ENABLED = False
DOWNLOAD_MAXSIZE = 1*1024*1024

# auto throttling
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_DEBUG = False
AUTOTHROTTLE_MAX_DELAY = 3.0
AUTOTHROTTLE_START_DELAY = 0.25
RANDOMIZE_DOWNLOAD_DELAY = False

# concurrency
CONCURRENT_REQUESTS = 64
CONCURRENT_REQUESTS_PER_DOMAIN = 10
DOWNLOAD_DELAY = 0.0

REACTOR_THREADPOOL_MAXSIZE = 32
DNS_TIMEOUT = 180

LOG_LEVEL = 'INFO'
