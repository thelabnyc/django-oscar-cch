.. _usage:

Usage
=====

.. _usage_simple_integration:

Simple Integration
------------------

The library includes a mix-in class that can be added to `order.utils.OrderCreator` to enable tax calculation as part of the order placement process. Override ``oscar.apps.order.utils.OrderCreator`` in ``order/utils.py`` and add the mix-in directly before the super class::

    from oscarcch.order_creator import CCHOrderCreatorMixin
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

SureTax Backend
---------------

:class:`SureTaxCalculator <oscarcch.suretax.SureTaxCalculator>` provides the same
interface as :class:`CCHTaxCalculator <oscarcch.calculator.CCHTaxCalculator>`, but
calculates taxes using the CCH SureTax General Merchandise REST API instead of the
CCH Sales Tax Office SOAP API. It requires the ``SURETAX_API_BASE_URL``,
``SURETAX_CLIENT_NUMBER``, and ``SURETAX_VALIDATION_KEY`` settings.::

    from oscarcch.suretax import SureTaxCalculator
    from oscarcch.models import OrderTaxation


    suretax_response = SureTaxCalculator().apply_taxes(shipping_address, basket)
    is_tax_known = (suretax_response is not None)

    # ...

    if is_tax_known:
        OrderTaxation.save_details(order, suretax_response)

Calculations are quote-only (``ReturnFileCode: "Q"``): nothing is recorded on the
SureTax side for compliance reporting, matching the behavior of the default
``CCH_FINALIZE_TRANSACTION = False`` in the SOAP backend.

:class:`CCHOrderCreatorMixin <oscarcch.order_creator.CCHOrderCreatorMixin>` uses
``CCHTaxCalculator`` during order placement by default. To use SureTax in checkout,
override ``get_tax_calculator`` on the integrating project's ``OrderCreator``::

    class OrderCreator(CCHOrderCreatorMixin, CoreOrderCreator):
        def get_tax_calculator(self):
            return SureTaxCalculator()
