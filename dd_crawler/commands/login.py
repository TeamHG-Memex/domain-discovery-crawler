from scrapy import Request
from scrapy.commands import ScrapyCommand
from scrapy.exceptions import UsageError
from scrapy_redis.scheduler import Scheduler


def add_login(spider, url, login, password, queue=None):
    print('Adding login url: {}'.format(url))
    if queue is None:
        queue = spider.queue
    queue.add_login_credentials(url, login, password)
    # push some known url from this domain to make sure we re-crawl it
    # while logged-in
    queue.push(Request(url=url, priority=spider.initial_priority))


class Command(ScrapyCommand):
    requires_project = True

    def syntax(self):
        return '<spider> <url> <login> <password>'

    def short_desc(self):
        return 'Specify login credentials at given url'

    def run(self, args, opts):
        if len(args) != 4:
            raise UsageError()
        spider_name, url, login, password = args

        crawler = self.crawler_process.create_crawler(spider_name)
        scheduler = Scheduler.from_settings(self.settings)
        spider = crawler.spidercls.from_crawler(crawler)
        scheduler.open(spider)

        add_login(spider, url, login, password, queue=scheduler.queue)
