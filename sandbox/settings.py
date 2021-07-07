from django.utils.translation import gettext_lazy as _
from oscar.defaults import *  # noqa
from psycopg2cffi import compat
import os

compat.register()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEBUG = True
SECRET_KEY = "li0$-gnv)76g$yf7p@(cg-^_q7j6df5cx$o-gsef5hd68phj!4"
SITE_ID = 1

USE_I18N = True
LANGUAGE_CODE = "en-us"
LANGUAGES = (
    ("en-us", _("English")),
    ("es", _("Spanish")),
)

# Configure JUnit XML output
TEST_RUNNER = "xmlrunner.extra.djangotestrunner.XMLTestRunner"
_tox_env_name = os.environ.get("TOX_ENV_NAME")
if _tox_env_name:
    TEST_OUTPUT_DIR = os.path.join(BASE_DIR, f"../junit-{_tox_env_name}/")
else:
    TEST_OUTPUT_DIR = os.path.join(BASE_DIR, "../junit/")

INSTALLED_APPS = [
    # Core Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.postgres",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.flatpages",
    # django-oscar
    "oscar",
    "oscar.apps.analytics",
    "oscar.apps.communication",
    "oscar.apps.checkout",
    "oscar.apps.address",
    "oscar.apps.shipping",
    "oscar.apps.catalogue",
    "oscar.apps.catalogue.reviews",
    "oscar.apps.partner",
    "oscar.apps.basket",
    "oscar.apps.payment",
    "oscar.apps.offer",
    "order",  # 'oscar.apps.order',
    "oscar.apps.customer",
    "oscar.apps.search",
    "oscar.apps.voucher",
    "oscar.apps.wishlists",
    "oscar.apps.dashboard",
    "oscar.apps.dashboard.reports",
    "oscar.apps.dashboard.users",
    "oscar.apps.dashboard.orders",
    "oscar.apps.dashboard.catalogue",
    "oscar.apps.dashboard.offers",
    "oscar.apps.dashboard.partners",
    "oscar.apps.dashboard.pages",
    "oscar.apps.dashboard.ranges",
    "oscar.apps.dashboard.reviews",
    "oscar.apps.dashboard.vouchers",
    "oscar.apps.dashboard.communications",
    "oscar.apps.dashboard.shipping",
    # 3rd-party apps that oscar depends on
    "widget_tweaks",
    "haystack",
    "treebeard",
    "sorl.thumbnail",
    "django_tables2",
    "oscarcch",
]

MIDDLEWARE = (
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "oscar.apps.basket.middleware.BasketMiddleware",
)

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "oscar.apps.search.context_processors.search_form",
                "oscar.apps.checkout.context_processors.checkout",
                "oscar.apps.communication.notifications.context_processors.notifications",
                "oscar.core.context_processors.metadata",
            ],
        },
    },
]

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": "postgres",
        "USER": "postgres",
        "PASSWORD": "",
        "HOST": "postgres",
        "PORT": 5432,
    }
}

HAYSTACK_CONNECTIONS = {
    "default": {
        "ENGINE": "haystack.backends.simple_backend.SimpleEngine",
    },
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "cch-testing-sandbox",
    }
}

CCH_WSDL = "file://%s" % os.path.join(BASE_DIR, "wsdl/cch.xml")
CCH_ENTITY = "TESTSANDBOX"
CCH_DIVISION = "42"
CCH_PRODUCT_SKU = "ABC123"
CCH_TIME_ZONE = "America/New_York"
