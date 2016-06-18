FROM ubuntu:14.04

RUN apt-get update && \
    apt-get install -y dnsmasq

COPY ./dnsmasq.conf /etc/
COPY ./resolv.dnsmasq /etc/

# -d means "no daemon"
CMD dnsmasq -d