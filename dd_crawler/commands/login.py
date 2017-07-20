from scrapy.commands import ScrapyCommand
from scrapy.exceptions import UsageError
from scrapy_redis.scheduler import Scheduler


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

        scheduler.queue.add_login_credentials(url, login, password)
        print('Added login url: {}'.format(url))
