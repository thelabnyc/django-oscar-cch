Django Settings
===============

All settings in ``oscarcch.settings`` can be overridden by in your Django project's settings file.

Connection Settings
-------------------

.. autodata:: oscarcch.settings.CCH_WSDL
.. autodata:: oscarcch.settings.CCH_MAX_RETRIES
.. autodata:: oscarcch.settings.CCH_ENTITY
.. autodata:: oscarcch.settings.CCH_DIVISION
.. autodata:: oscarcch.settings.CCH_SOURCE_SYSTEM

Transaction Settings
--------------------

.. autodata:: oscarcch.settings.CCH_TEST_TRANSACTIONS
.. autodata:: oscarcch.settings.CCH_TRANSACTION_TYPE
.. autodata:: oscarcch.settings.CCH_CUSTOMER_TYPE
.. autodata:: oscarcch.settings.CCH_PROVIDER_TYPE
.. autodata:: oscarcch.settings.CCH_FINALIZE_TRANSACTION

Product Taxation Settings
-------------------------

.. autodata:: oscarcch.settings.CCH_PRODUCT_SKU
.. autodata:: oscarcch.settings.CCH_PRODUCT_GROUP
.. autodata:: oscarcch.settings.CCH_PRODUCT_ITEM
.. autodata:: oscarcch.settings.CCH_SHIPPING_SKU
.. autodata:: oscarcch.settings.CCH_SHIPPING_TAXES_ENABLED

Other Settings
--------------

.. autodata:: oscarcch.settings.CCH_PRECISION
.. autodata:: oscarcch.settings.CCH_POSTALCODE_LENGTH
.. autodata:: oscarcch.settings.CCH_TIME_ZONE

SureTax Settings
----------------

:class:`SureTaxCalculator <oscarcch.suretax.SureTaxCalculator>` also honours the
shared ``CCH_PRECISION``, ``CCH_TIME_ZONE``, ``CCH_PRODUCT_SKU``, ``CCH_SHIPPING_SKU``
and ``CCH_SHIPPING_TAXES_ENABLED`` settings above.

.. autodata:: oscarcch.settings.SURETAX_API_BASE_URL
.. autodata:: oscarcch.settings.SURETAX_CLIENT_NUMBER
.. autodata:: oscarcch.settings.SURETAX_VALIDATION_KEY
.. autodata:: oscarcch.settings.SURETAX_BUSINESS_UNIT
.. autodata:: oscarcch.settings.SURETAX_CLIENT_TRACKING
.. autodata:: oscarcch.settings.SURETAX_TIMEOUT
.. autodata:: oscarcch.settings.SURETAX_MAX_RETRIES
.. autodata:: oscarcch.settings.SURETAX_TAX_NAME_MAP
