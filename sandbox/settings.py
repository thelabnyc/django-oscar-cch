from oscar.defaults import *  # noqa
from oscar import OSCAR_MAIN_TEMPLATE_DIR, get_core_apps
import os

DEBUG = True
SECRET_KEY = 'li0$-gnv)76g$yf7p@(cg-^_q7j6df5cx$o-gsef5hd68phj!4'
SITE_ID = 1

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.postgres',
    'cch',
] + get_core_apps(['order'])


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            OSCAR_MAIN_TEMPLATE_DIR
        ],
        'APP_DIRS': True,
    },
]


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'postgres',
        'USER': 'postgres',
        'PASSWORD': '',
        'HOST': 'postgres',
        'PORT': 5432,
    }
}

HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': 'haystack.backends.simple_backend.SimpleEngine',
    },
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'cch-testing-sandbox',
    }
}


SOAP_PROXY_URL = os.environ.get('SOAP_PROXY_URL')
CCH_WSDL = os.environ.get('CCH_WSDL')
CCH_ENTITY = os.environ.get('CCH_ENTITY')
CCH_DIVISION = os.environ.get('CCH_DIVISION')
CCH_PRODUCT_SKU = os.environ.get('CCH_PRODUCT_SKU')
