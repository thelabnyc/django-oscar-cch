.. _usage:

Usage
=====

.. _usage_simple_integration:

Simple Integration
------------------

The library includes a mix-in class that can be added to `order.utils.OrderCreator` to enable tax calculation as part of the order placement process. Override ``oscar.apps.order.utils.OrderCreator`` in ``order/utils.py`` and add the mix-in directly before the super class::

    from oscarcch.mixins import CCHOrderCreatorMixin
    from oscar.apps.order import utils


    class OrderCreator(CCHOrderCreatorMixin, utils.OrderCreator):
        pass


Custom Integration
------------------

For more complicated needs, you can interface with the tax calculation API directly. :class:`CCHTaxCalculator <oscarcch.calculator.CCHTaxCalculator>` is used to apply taxes to a user's basket.::

    from oscarcch.calculator import CCHTaxCalculator
    from oscarcch.models import OrderTaxation


    # Take a basket and the customer's shipping address and apply taxes to the basket. If the call
    # to the CCH server fails for any reason, tax will be set to 0 and the method will return None.
    # In normal cases, the method will return the details of the taxes applied.
    cch_response = CCHTaxCalculator().apply_taxes(shipping_address, basket)
    is_tax_known = (cch_response is not None)

    # ...
    # Do other things necessary to convert the basket into an order
    # ...

    # Take the tax details generated earlier and save them into the DB.
    if is_tax_known:
        OrderTaxation.save_details(order, cch_response)
