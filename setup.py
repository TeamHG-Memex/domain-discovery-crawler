from setuptools import setup


setup(
    name='dd_crawler',
    packages=['dd_crawler'],
    install_requires=[
        'scrapy>=1.1.0',
        'scrapy-cdr',
        'scrapy-redis',
    ],
)
