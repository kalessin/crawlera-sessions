# Automatically created by: shub deploy

from setuptools import setup, find_packages

setup(
    name         = 'crawlera-session',
    version      = '1.2.4',
    description  = 'Class that provides decorators and functions for easy handling of crawlera sessions in a scrapy spider.',
    long_description = open('README.md').read(),
    long_description_content_type = 'text/markdown',
    license      = 'BSD',
    author       = 'Martin Olveyra',
    author_email = 'molveyra@gmail.com',
    url          = 'https://github.com/kalessin/crawlera-sessions',
    packages     = find_packages(),
    scripts = [],
    classifiers = [
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
    ]
)
