from setuptools import setup


setup(
    name='dd_crawler',
    packages=['dd_crawler'],
    install_requires=[
        'autopager',
        # 'deepdeep',
        'html_text>=0.2.1',
        'json-lines>=0.3.1',
        'numpy',
        'pySmaz==1.0.0',
        'scrapy-cdr>=0.4.0',
        'scrapy-redis>=0.6.8',
        'scrapy>=1.1.0',
        'tldextract',
        'vmprof',
    ],
)
