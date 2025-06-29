from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings


def overridable(name: str, default: Any = None, required: bool = False) -> Any:
    if required:
        if not hasattr(settings, name) or not getattr(settings, name):
            raise AttributeError(
                "Attribute %s must be defined in Django settings" % name
            )
    return getattr(settings, name, default)


#: Full URL of the CCH WSDL.
CCH_WSDL: str = overridable("CCH_WSDL", required=True)

#: Optional: http(s) proxy url
CCH_PROXY_URL: str | None = overridable("CCH_PROXY_URL")

# SOAP WSDL-open timeout.
CCH_OPEN_TIMEOUT: tuple[float, float] = overridable("CCH_OPEN_TIMEOUT", (3.05, 10))

# SOAP method-call timeout.
CCH_SEND_TIMEOUT: tuple[float, float] = overridable("CCH_SEND_TIMEOUT", (3.05, 10))

#: Max number of times to retry to calculate tax before giving up.
CCH_MAX_RETRIES: int = overridable("CCH_MAX_RETRIES", 2)

#: Default entity code to send to CCH.
CCH_ENTITY: str = overridable("CCH_ENTITY", required=True)

#: Default division code to send to CCH.
CCH_DIVISION: str = overridable("CCH_DIVISION", required=True)

#: Name of the source system to send to CCH. Defaults to `Oscar`.
CCH_SOURCE_SYSTEM: str = overridable("CCH_SOURCE_SYSTEM", "Oscar")

#: Whether or not to set the test flag in CCH requests. Defaults to the same value as Django's ``DEBUG`` setting.
CCH_TEST_TRANSACTIONS: bool = overridable("CCH_TEST_TRANSACTIONS", settings.DEBUG)

#: CCH Transaction Type Code. Defaults to ``01``.
CCH_TRANSACTION_TYPE: str = overridable("CCH_TRANSACTION_TYPE", "01")

#: CCH Customer Type. Defaults to ``08``.
CCH_CUSTOMER_TYPE: str = overridable("CCH_CUSTOMER_TYPE", "08")

#: CCH Provider Type. Defaults to ``70``.
CCH_PROVIDER_TYPE: str = overridable("CCH_PROVIDER_TYPE", "70")

#: Whether or not to set the CCH finalize transaction flag. Defaults to False.
CCH_FINALIZE_TRANSACTION: bool = overridable("CCH_FINALIZE_TRANSACTION", False)

#: Default CCH Product SKU. Can be overridden by creating and setting a Product attribute called cch_product_sku.
CCH_PRODUCT_SKU: str = overridable("CCH_PRODUCT_SKU", "")

#: Default CCH Product Group Code. Can be overridden by creating and setting a Product attribute called cch_product_group.
CCH_PRODUCT_GROUP: str = overridable("CCH_PRODUCT_GROUP", "")

#: Default CCH Product Item Code. Can be overridden by creating and setting a Product attribute called cch_product_item.
CCH_PRODUCT_ITEM: str = overridable("CCH_PRODUCT_ITEM", "")

#: Default CCH Shipping Charge SKU.
CCH_SHIPPING_SKU: str = overridable("CCH_SHIPPING_SKU", "PARCEL")

#: Enable/Disable tax calculation on shipping feed
CCH_SHIPPING_TAXES_ENABLED: bool = overridable("CCH_SHIPPING_TAXES_ENABLED", True)

#: Decimal precision to use when sending prices to CCH. Defaults to two-decimal places.
CCH_PRECISION: Decimal = overridable("CCH_PRECISION", Decimal(".01"))

#: Max length of postal-codes to send to CCH. Defaults to ``5``. All digits and characters after this limit will
#: be clipped in the SOAP request.
CCH_POSTALCODE_LENGTH: int = overridable("CCH_POSTALCODE_LENGTH", 5)

#: Timezone to use for date times sent to CCH. Defaults to ``UTC``.
CCH_TIME_ZONE = ZoneInfo(overridable("CCH_TIME_ZONE", "UTC"))
