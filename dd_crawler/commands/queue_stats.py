import json

from scrapy.commands import ScrapyCommand
from scrapy.exceptions import UsageError

from scrapy_redis.scheduler import Scheduler


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
        print_top = 10
        printed_count = 0
        queues = stats['queues']
        print('{:<50}\tCount\tScore'.format('Domain'))
        for queue, score, count in queues[:print_top]:
            printed_count += count
            domain = queue.rsplit(':')[-1]
            print('{:<50}\t{}\t{:.0f}'.format(domain, count, score))
        others_count = sum(count for _, _, count in queues) - printed_count
        if others_count:
            print('...')
            print('{:<50}\t{}'.format(
                'other {}:'.format(len(queues) - print_top), others_count))
            print()

        if opts.output:
            with open(opts.output, 'w') as f:
                json.dump(stats, f,
                          ensure_ascii=False, indent=True, sort_keys=True)
            print('Stats dumped to {}'.format(opts.output))
