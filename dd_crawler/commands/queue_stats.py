import json

from scrapy.commands import ScrapyCommand
from scrapy.exceptions import UsageError

from scrapy_redis.scheduler import Scheduler
from dd_crawler.queue import RequestQueue


class Command(ScrapyCommand):
    requires_project = True

    def syntax(self):
        return '<spider>'

    def add_options(self, parser):
        ScrapyCommand.add_options(self, parser)
        parser.add_option('-o', '--output',
                          help='dump stats into json file (use - for stdout)')

    def short_desc(self):
        return 'Print short summary, dump queue stats to a file'

    def run(self, args, opts):
        if len(args) != 1:
            raise UsageError()

        crawler = self.crawler_process.create_crawler(args[0])
        scheduler = Scheduler.from_settings(self.settings)
        spider = crawler.spidercls.from_crawler(crawler)
        scheduler.open(spider)
        stats = scheduler.queue.get_stats()

        print('\nQueue size: {len}, domains: {n_domains}\n'.format(**stats))
        printed_count = 0
        print('{:<50}\tCount\tScore'.format('Domain'))
        for queue, score, count in stats['queues'][:10]:
            printed_count += count
            domain = queue.rsplit(':')[-1]
            print('{:<50}\t{}\t{:.0f}'.format(domain, count, score))
        other = sum(count for _, _, count in stats['queues']) - printed_count
        if other:
            print('...')
            print('{:<50}\t{}'.format('other:', other))
            print()

        if opts.output:
            with open(opts.output, 'w') as f:
                json.dump(stats, f,
                          ensure_ascii=False, indent=True, sort_keys=True)
            print('Stats dumped to {}'.format(opts.output))
