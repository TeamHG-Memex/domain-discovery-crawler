FROM python:3.5

WORKDIR /dd_crawler

RUN apt-get update && \
    apt-get install -y dnsmasq

COPY ./requirements.txt .

RUN pip install -U pip setuptools wheel && \
    pip install -r requirements.txt

COPY ./dnsmasq/dnsmasq.conf /etc/
COPY ./dnsmasq/resolv.dnsmasq /etc/

COPY . .

RUN pip install -e .
