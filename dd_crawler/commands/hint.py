from scrapy.commands import ScrapyCommand
from scrapy.exceptions import UsageError
from scrapy_redis.scheduler import Scheduler


class Command(ScrapyCommand):
    requires_project = True

    def syntax(self):
        return '<spider> (pin|unpin) <url>'

    def short_desc(self):
        return 'Add or remove hint url'

    def run(self, args, opts):
        if len(args) != 3:
            raise UsageError()
        spider_name, action, url = args
        if action not in {'pin', 'unpin'}:
            raise UsageError()

        crawler = self.crawler_process.create_crawler(spider_name)
        scheduler = Scheduler.from_settings(self.settings)
        spider = crawler.spidercls.from_crawler(crawler)
        scheduler.open(spider)

        if action == 'pin':
            scheduler.queue.add_hint_url(url)
            print('Added hint url: {}'.format(url))
        else:
            scheduler.queue.remove_hint_url(url)
            print('Removed hint url: {}'.format(url))
