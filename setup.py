#!/usr/bin/env python
from setuptools import setup, find_packages, Distribution
import codecs
import os.path

# Make sure versiontag exists before going any further
Distribution().fetch_build_eggs('versiontag>=1.2.0')

from versiontag import get_version, cache_git_tag  # NOQA


packages = find_packages()

install_requires = [
    'django-oscar>=1.3',
    'django-statsd-mozilla>=0.3.16',
    'instrumented-soap>=1.1.0',
]

extras_require = {
    'development': [
        'psycopg2>=2.6.2',
        'flake8>=3.2.1',
        'freezegun>=0.3.8',
        'lxml>=3.7.2',
        'sphinx>=1.5.2',
        'versiontag>=1.2.0',
    ],
}


def fpath(name):
    return os.path.join(os.path.dirname(__file__), name)


def read(fname):
    return codecs.open(fpath(fname), encoding='utf-8').read()


cache_git_tag()

setup(
    name='django-oscar-cch',
    description="Integration between django-oscar and the CCH Sales Tax Office SOAP API.",
    version=get_version(pypi=True),
    long_description=open('README.rst').read(),
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Framework :: Django :: 1.8',
        'Framework :: Django :: 1.9',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: ISC License (ISCL)',
        'Operating System :: Unix',
        'Operating System :: MacOS :: MacOS X',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
    author='Craig Weber',
    author_email='crgwbr@gmail.com',
    url='https://gitlab.com/thelabnyc/django-oscar-cch',
    license='ISC',
    packages=packages,
    install_requires=install_requires,
    extras_require=extras_require,
)
