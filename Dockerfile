FROM python:3.5

WORKDIR /dd_crawler

RUN apt-get update && \
    apt-get install -y dnsmasq redis-tools

RUN pip install -U pip setuptools wheel && \
    pip install numpy pandas scrapy

COPY ./requirements.txt .
RUN pip install -r requirements.txt && \
    formasaurus init

COPY ./docker/deep-deep-0.0.tar.gz .
RUN pip install deep-deep-0.0.tar.gz

COPY ./docker/dnsmasq.conf /etc/
COPY ./docker/resolv.dnsmasq /etc/

COPY . .

RUN pip install -e .

ENTRYPOINT /bin/bash /dd_crawler/docker/crawl.sh
