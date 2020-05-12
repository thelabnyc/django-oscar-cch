from django.db import models, transaction
from oscar.core.loading import get_class
from .calculator import CCHTaxCalculator
from .models import OrderTaxation
from .prices import ShippingCharge

OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')



class CCHOrderMixin(models.Model):
    is_tax_known = models.BooleanField(default=True)

    class Meta:
        abstract = True


class CCHOrderLineMixin(models.Model):
    basket_line = models.OneToOneField('basket.Line',
        related_name='order_line',
        on_delete=models.SET_NULL,
        null=True)

    class Meta:
        abstract = True


class CCHOrderCreatorMixin(object):
    def place_order(self, basket, total,  # noqa (too complex (12))
                    shipping_method, shipping_charge, user=None,
                    shipping_address=None, billing_address=None,
                    order_number=None, status=None, **kwargs):
        # Calculate the tax liability for this shipping address
        if not isinstance(shipping_charge, ShippingCharge):
            shipping_charge = ShippingCharge(
                currency=shipping_charge.currency,
                excl_tax=shipping_charge.excl_tax)
        cch_response = CCHTaxCalculator().apply_taxes(
            shipping_address=shipping_address,
            basket=basket,
            shipping_charge=shipping_charge)
        is_tax_known = (cch_response is not None)

        # Update order total now that we now taxes
        total = OrderTotalCalculator().calculate(basket, shipping_charge)

        with transaction.atomic():
            # Save order and line records
            order = super().place_order(
                basket, total,
                shipping_method, shipping_charge, user,
                shipping_address, billing_address,
                order_number, status, is_tax_known=is_tax_known, **kwargs)

            # Save order taxation details
            if is_tax_known:
                OrderTaxation.save_details(order, cch_response)

        return order


    def create_line_models(self, order, basket_line, extra_line_fields=None):
        order_line = super().create_line_models(order, basket_line, extra_line_fields)
        order_line.basket_line = basket_line
        order_line.save()
        return order_line
