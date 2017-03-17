.. _installation:

Installation
============


Caveats
-------

1. You must fork the `order` application from Oscar to enable tax calculation as part of placing an order.
2. Persistence of tax details, while optional, requires that your project uses PostgreSQL. It relies on the HStore field.


Installation Guide
------------------

1. Install the ``django-oscar-cch`` package.::

    $ pip install django-oscar-cch

2. Add ``oscarcch`` to your ``INSTALLED_APPS``::

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
        'oscarcch',
        ...
    ] + get_core_apps([
        ...
    ])
    ...

3. Add some attributes to ``settings.py`` to configure how the application should connect to CCH.::

    # myproject/settings.py

    # Add this is you need to connect to the SOAP API through an HTTP Proxy.
    # See the instrumented-soap documentation for more details.
    SOAP_PROXY_URL = ...

    # Configure the CCH WSDL location, entity, and division code
    CCH_WSDL = ...
    CCH_ENTITY = ...
    CCH_DIVISION = ...

    # Provide either a product SKU or a product group and item to send to CCH when calculating taxes
    CCH_PRODUCT_SKU = ...
    CCH_PRODUCT_GROUP = ...
    CCH_PRODUCT_ITEM = ...

4. Alternative to setting ``CCH_PRODUCT_SKU``, ``CCH_PRODUCT_GROUP``, and ``CCH_PRODUCT_ITEM`` globally, you can set them per-product by creating ProductClass attributes with the same names (in lowercase).

5. Install the necessary extra fields on ``order.models.Order`` and ``order.models.Line`` (see also `How to fork Oscar apps <https://django-oscar.readthedocs.org/en/releases-1.1/topics/customisation.html#fork-the-oscar-app>`_).::

    # order/models.py

    from oscarcch.mixins import CCHOrderMixin, CCHOrderLineMixin
    from oscar.apps.order.abstract_models import AbstractOrder, AbstractLine

    class Order(CCHOrderMixin, AbstractOrder):
        pass

    class Line(CCHOrderLineMixin, AbstractLine):
        pass

    from oscar.apps.order.models import *  # noqa

6. Create and run migrations for the `order` app.::

    $ python manage.py makemigrations order
    $ python manage.py migrate


For usage, continue to :ref:`usage`.
