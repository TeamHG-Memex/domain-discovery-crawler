from setuptools import setup


setup(
    name='dd_crawler',
    packages=['dd_crawler'],
    install_requires=[
        'autopager',
        # 'deepdeep',
        'html_text>=0.2.1',
        'numpy',
        'scrapy-cdr',
        'scrapy-redis>=0.6.8',
        'scrapy>=1.1.0',
        'tldextract',
        'vmprof',
    ],
)
