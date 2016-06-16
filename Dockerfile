FROM python:3.5

WORKDIR /dd_crawler

COPY ./requirements.txt .

RUN pip install -U pip setuptools wheel && \
    pip install -r requirements.txt

COPY . .

RUN pip install -e .
