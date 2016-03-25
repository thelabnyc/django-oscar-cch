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


Changelog
=========


1.0.0 (2016-01-25)
------------------
Initial release.
