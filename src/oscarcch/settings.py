from decimal import Decimal
from django.conf import settings
import pytz


def overridable(name, default=None, required=False):
    if required:
        if not hasattr(settings, name) or not getattr(settings, name):
            raise AttributeError("Attribute %s must be defined in Django settings" % name)
    return getattr(settings, name, default)


#: Full URL of the CCH WSDL.
CCH_WSDL = overridable('CCH_WSDL', required=True)

#: Max number of times to retry to calculate tax before giving up.
CCH_MAX_RETRIES = overridable('CCH_MAX_RETRIES', 2)

#: Default entity code to send to CCH.
CCH_ENTITY = overridable('CCH_ENTITY', required=True)

#: Default division code to send to CCH.
CCH_DIVISION = overridable('CCH_DIVISION', required=True)

#: Name of the source system to send to CCH. Defaults to `Oscar`.
CCH_SOURCE_SYSTEM = overridable('CCH_SOURCE_SYSTEM', 'Oscar')

#: Whether or not to set the test flag in CCH requests. Defaults to the same value as Django's ``DEBUG`` setting.
CCH_TEST_TRANSACTIONS = overridable('CCH_TEST_TRANSACTIONS', settings.DEBUG)

#: CCH Transaction Type Code. Defaults to ``01``.
CCH_TRANSACTION_TYPE = overridable('CCH_TRANSACTION_TYPE', '01')

#: CCH Customer Type. Defaults to ``08``.
CCH_CUSTOMER_TYPE = overridable('CCH_CUSTOMER_TYPE', '08')

#: CCH Provider Type. Defaults to ``70``.
CCH_PROVIDER_TYPE = overridable('CCH_PROVIDER_TYPE', '70')

#: Whether or not to set the CCH finalize transaction flag. Defaults to False.
CCH_FINALIZE_TRANSACTION = overridable('CCH_FINALIZE_TRANSACTION', False)

#: Default CCH Product SKU. Can be overridden by creating and setting a Product attribute called cch_product_sku.
CCH_PRODUCT_SKU = overridable('CCH_PRODUCT_SKU', '')

#: Default CCH Product Group Code. Can be overridden by creating and setting a Product attribute called cch_product_group.
CCH_PRODUCT_GROUP = overridable('CCH_PRODUCT_GROUP', '')

#: Default CCH Product Item Code. Can be overridden by creating and setting a Product attribute called cch_product_item.
CCH_PRODUCT_ITEM = overridable('CCH_PRODUCT_ITEM', '')

#: When using the :ref:`usage_simple_integration`, this controls whether or not to allow placing an order when the call to
#: CCH for tax calculation fails or times out. Defaults to ``True``. When ``False`` and an error occurs,
#: OrderCreator.place_order will raise an Exception.
CCH_TOLERATE_FAILURE_DURING_PLACE_ORDER = overridable('CCH_TOLERATE_FAILURE_DURING_PLACE_ORDER', True)

#: Decimal precision to use when sending prices to CCH. Defaults to two-decimal places.
CCH_PRECISION = overridable('CCH_PRECISION', Decimal('.01'))

#: Max length of postal-codes to send to CCH. Defaults to ``5``. All digits and characters after this limit will
#: be clipped in the SOAP request.
CCH_POSTALCODE_LENGTH = overridable('CCH_POSTALCODE_LENGTH', 5)

#: Timezone to use for date times sent to CCH. Defaults to ``UTC``.
CCH_TIME_ZONE = pytz.timezone( overridable('CCH_TIME_ZONE', 'UTC') )
