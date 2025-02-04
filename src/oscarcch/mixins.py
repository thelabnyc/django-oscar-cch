from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.db import models, transaction
from oscar.core.loading import get_class
from oscar.core.prices import Price

from .calculator import CCHTaxCalculator
from .prices import ShippingCharge

if TYPE_CHECKING:
    from django.contrib.auth.models import User
    from oscar.apps.basket.models import Basket
    from oscar.apps.checkout.calculators import OrderTotalCalculator
    from oscar.apps.order.models import BillingAddress
    from oscar.apps.order.models import Line as OrderLine
    from oscar.apps.order.models import Order, ShippingAddress
    from oscar.apps.order.utils import OrderCreator
    from oscar.apps.shipping.methods import Base as BaseShippingMethod
else:
    OrderTotalCalculator = get_class("checkout.calculators", "OrderTotalCalculator")
    OrderCreator = object


class CCHOrderMixin(models.Model):
    is_tax_known = models.BooleanField(default=True)

    class Meta:
        abstract = True


class CCHOrderLineMixin(models.Model):
    basket_line = models.OneToOneField(
        "basket.Line",
        related_name="order_line",
        on_delete=models.SET_NULL,
        null=True,
    )

    class Meta:
        abstract = True


class CCHOrderCreatorMixin(OrderCreator):
    def place_order(  # type:ignore[override]
        self,
        basket: "Basket",
        total: Decimal,  # noqa (too complex (12))
        shipping_method: "BaseShippingMethod",
        shipping_charge: ShippingCharge | Price,
        user: "User | None" = None,
        shipping_address: "ShippingAddress | None" = None,
        billing_address: "BillingAddress | None" = None,
        order_number: str | None = None,
        status: str | None = None,
        **kwargs: Any,
    ) -> "Order":
        # Calculate the tax liability for this shipping address
        if not isinstance(shipping_charge, ShippingCharge):
            shipping_charge = ShippingCharge(
                currency=shipping_charge.currency, excl_tax=shipping_charge.excl_tax
            )
        cch_response = CCHTaxCalculator().apply_taxes(
            shipping_address=shipping_address,
            basket=basket,
            shipping_charge=shipping_charge,
        )
        is_tax_known = cch_response is not None

        # Update order total now that we now taxes
        total = OrderTotalCalculator().calculate(basket, shipping_charge)

        with transaction.atomic():
            # Save order and line records
            order = super().place_order(
                basket,
                total,
                shipping_method,
                shipping_charge,
                user,
                shipping_address,
                billing_address,
                order_number,
                status,
                is_tax_known=is_tax_known,
                **kwargs,
            )

            # Save order taxation details
            if is_tax_known and cch_response is not None:
                from .models import OrderTaxation

                OrderTaxation.save_details(order, cch_response)

        return order

    def create_line_models(
        self,
        order: "Order",
        basket_line: "OrderLine",
        extra_line_fields: dict[str, Any] | None = None,
    ) -> "OrderLine":
        order_line = super().create_line_models(order, basket_line, extra_line_fields)
        order_line.basket_line = basket_line
        order_line.save()
        return order_line
