from decimal import Decimal
from django.conf import settings
import pytz

def overridable(name, default=None, required=False):
    if required:
        if not hasattr(settings, name) or not getattr(settings, name):
            raise AttributeError("Attribute %s must be defined in Django settings" % name)
    return getattr(settings, name, default)


CCH_CACHE_BACKEND = overridable('CCH_CACHE_BACKEND', 'default')
CCH_ESTIMATE_CACHE_SECONDS = overridable('CCH_ESTIMATE_CACHE_SECONDS', 14400)
CCH_BASKET_UAT_CACHE_SECONDS = overridable('CCH_BASKET_UAT_CACHE_SECONDS', 86400)
CCH_WSDL = overridable('CCH_WSDL', required=True)
CCH_ENTITY = overridable('CCH_ENTITY', required=True)
CCH_DIVISION = overridable('CCH_DIVISION', required=True)
CCH_SOURCE_SYSTEM = overridable('CCH_SOURCE_SYSTEM', 'Oscar')
CCH_TEST_TRANSACTIONS = overridable('CCH_TEST_TRANSACTIONS', settings.DEBUG)
CCH_TRANSACTION_TYPE = overridable('CCH_TRANSACTION_TYPE', '01')
CCH_CUSTOMER_TYPE = overridable('CCH_CUSTOMER_TYPE', '08')
CCH_PROVIDER_TYPE = overridable('CCH_PROVIDER_TYPE', '70')
CCH_FINALIZE_TRANSACTION = overridable('CCH_FINALIZE_TRANSACTION', False)
CCH_PRODUCT_SKU = overridable('CCH_PRODUCT_SKU', '')
CCH_PRODUCT_GROUP = overridable('CCH_PRODUCT_GROUP', '')
CCH_PRODUCT_ITEM = overridable('CCH_PRODUCT_ITEM', '')
CCH_TOLERATE_FAILURE_DURING_PLACE_ORDER = overridable('CCH_TOLERATE_FAILURE_DURING_PLACE_ORDER', True)
CCH_PRECISION = overridable('CCH_PRECISION', Decimal('.01'))
CCH_POSTALCODE_LENGTH = overridable('CCH_POSTALCODE_LENGTH', 5)
CCH_TIME_ZONE = pytz.timezone( overridable('CCH_TIME_ZONE', 'UTC') )
