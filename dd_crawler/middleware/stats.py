import json
from pathlib import Path

from scrapy.exceptions import NotConfigured
from scrapy_cdr import CDRItem

from dd_crawler.utils import get_domain


class SpiderStatsMiddleware:
    def __init__(self, *, stats_path: str, relevancy_threshold: float):
        self.domains = set()
        self.relevant_domains = set()
        self.total_score = 0.
        self.n_crawled = 0
        self.stats_file = Path(stats_path).open('at')
        self.relevancy_threshold = relevancy_threshold

    @classmethod
    def from_crawler(cls, crawler):
        stats_path = crawler.settings.get('SPIDER_STATS_PATH')
        if not stats_path:
            raise NotConfigured('SPIDER_STATS_PATH not defined')
        threshold = crawler.settings.getfloat('PAGE_RELEVANCY_THRESHOLD', 0.5)
        return cls(stats_path=stats_path, relevancy_threshold=threshold)

    def process_spider_output(self, response, result, spider):
        for item in result:
            if isinstance(item, CDRItem):
                self.n_crawled += 1
                domain = get_domain(item['url'])
                self.domains.add(domain)
                score = item.get('extracted_metadata', {}).get('page_score', 0.)
                self.total_score += score
                if score > self.relevancy_threshold:
                    self.relevant_domains.add(domain)
            yield item
        self.dump_stats()

    def dump_stats(self):
        self.stats_file.write('{}\n'.format(json.dumps({
            'n_domains': len(self.domains),
            'n_relevant_domains': len(self.relevant_domains),
            'n_crawled': self.n_crawled,
            'avg_score': self.total_score / self.n_crawled,
        }, sort_keys=True)))
        self.stats_file.flush()
