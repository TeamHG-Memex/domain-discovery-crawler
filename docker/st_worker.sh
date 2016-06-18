#!/bin/bash

set -e

# Wait for postgres
while ! nc -w 1 -z frontera-db 5432; do sleep 0.1; done

python -m frontera.worker.strategy \
    --config=dd_crawler.frontera.worker_settings \
    --strategy=frontera.worker.strategies.bfs.CrawlingStrategy \
    $*
