#!/usr/bin/env python3

import re
import sys
from functools import partial
from subprocess import check_output, CalledProcessError

check_output = partial(check_output, shell=True)


def main():
    ps = check_output('docker-compose ps', shell=True).decode('utf8')
    image_name = re.search(r'\b(\w+_crawler_1)\b', ps).groups()[0]
    try:
        print(check_output(
            'docker exec -it {} '
            'scrapy queue_stats deepdeep -s REDIS_HOST=redis {}'
            .format(image_name, ' '.join(sys.argv[1:])),
            shell=True).decode('utf8'))
    except CalledProcessError as e:
        print('Error', e.returncode, e.output.decode('utf8'),
              file=sys.stderr)


if __name__ == '__main__':
    main()
