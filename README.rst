=================
Instrumented SOAP
=================

This package is to handle integration between django-oscar based e-commerce sites and the `CCH Sales Tax Office <http://www.salestax.com/products/calculations-solutions/sales-tax-office.html>`_ SOAP API.


Caveats
=======

1. You must fork the `order` application from Oscar to enable tax calculation as part of placing an order.
2. Persistence of tax details, while optional, requires that your project uses PostgreSQL. It relies on the HStore field.


Installation
============


1. Install the `instrumented-soap` and `django-oscar-cch` packages.::

    $ pip install git+https://gitlab.com/thelabnyc/instrumented-soap.git#r1.0.0
    $ pip install git+https://gitlab.com/thelabnyc/django-oscar-cch.git#r1.0.0

2. Add `cch` to your `INSTALLED_APPS`::

    # myproject/settings.py
    ...
    INSTALLED_APPS = [
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.sites',
        'django.contrib.postgres',
        ...
        'cch',
        ...
    ] + get_core_apps([
        ...
    ])
    ...

3. Add some attributes to `settings.py` to configure how the application should connect to CCH.::

    # myproject/settings.py

    # Add this is you need to connect to the SOAP API through an HTTP Proxy
    SOAP_PROXY_URL = ...

    # Configure the CCH WSDL location, entity, and division code
    CCH_WSDL = ...
    CCH_ENTITY = ...
    CCH_DIVISION = ...

    # Provide either a product SKU or a product group and item to send to CCH when calculating taxes
    CCH_PRODUCT_SKU = ...
    CCH_PRODUCT_GROUP = ...
    CCH_PRODUCT_ITEM = ...

4. Install extra fields on order.models.Order and order.models.Line (see also `How to fork Oscar apps <https://django-oscar.readthedocs.org/en/releases-1.1/topics/customisation.html#fork-the-oscar-app>`_).::

    # order/models.py

    from cch.mixins import CCHOrderMixin, CCHOrderLineMixin
    from oscar.apps.order.abstract_models import AbstractOrder, AbstractLine

    class Order(CCHOrderMixin, AbstractOrder):
        pass

    class Line(CCHOrderLineMixin, AbstractLine):
        pass

    from oscar.apps.order.models import *  # noqa

5. Create and run migrations for the `order` app.::

    $ python managy.py makemigrations order
    $ python managy.py migrate


6. Add the CCH mixin to `order.utils.OrderCreator`.::

    # order/utils.py

    from cch.mixins import CCHOrderCreatorMixin
    from oscar.apps.order import utils


    class OrderCreator(CCHOrderCreatorMixin, utils.OrderCreator):
        pass


Usage
=====

`CCHTaxCalculator` is used to apply taxes to a user's basket.::

    from cch.calculator import CCHTaxCalculator
    from cch.models import OrderTaxation


    # Take a basket and the customer's shipping address and apply taxes to the basket. We can optionally
    # tolerate a failure to connect to the CCH server. In such a case, tax will be set to 0 and the method
    # will return none. In normal cases, the method will return the details of the taxes applied.
    cch_response = CCHTaxCalculator().apply_taxes(basket, shipping_address, ignore_cch_fail=True)
    is_tax_known = (cch_response is not None)

    # ...
    # Do other things necessary to convert the basket into an order
    # ...

    # Take the tax details generated earlier and save them into the DB.
    if is_tax_known:
        OrderTaxation.save_details(order, cch_response)

The `apply_taxes` method *always* sends a SOAP request to CCH. Is cases where you want to cache this call, for example, when exposing this functionality via an HTTP API, you can use the `estimate_taxes` method instead.::

    from cch.calculator import CCHTaxCalculator

    # This method returns a (sometimes hydrated from cache) basket with taxes applied. The cache is invalidated
    # automatically whenever a the basket or one of it's lines is saved. See cch.handlers for details.
    basket = CCHTaxCalculator().estimate_taxes(basket, shipping_address)


Changelog
=========

1.0.2
------------------

- Made `instrumented-soap` dependency optional.
- Moved gitlab testing from the shell executor to the docker executor.
- Added better usage documentation.

1.0.1
------------------

- Fixed an exception when `raven` isn't installed.

1.0.0
------------------

- Initial release.
