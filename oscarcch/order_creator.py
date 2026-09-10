from typing import TYPE_CHECKING, Any

from django.db import transaction
from oscar.core.loading import get_class, get_model
from oscar.core.prices import Price

from .calculator import CCHTaxCalculator
from .prices import ShippingCharge

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser

    from .suretax import SureTaxCalculator

Basket = get_model("basket", "Basket")
Order = get_model("order", "Order")
OrderLine = get_model("order", "Line")
ShippingAddress = get_model("order", "ShippingAddress")
BillingAddress = get_model("order", "BillingAddress")

OrderTotalCalculator = get_class("checkout.calculators", "OrderTotalCalculator")
OrderCreator = get_class("order.utils", "OrderCreator")
BaseShippingMethod = get_class("shipping.methods", "Base")


class CCHOrderCreatorMixin(OrderCreator):
    def get_tax_calculator(self) -> "CCHTaxCalculator | SureTaxCalculator":
        """
        Return the calculator :meth:`place_order` uses. Override to swap in
        :class:`SureTaxCalculator <oscarcch.suretax.SureTaxCalculator>`.
        """
        return CCHTaxCalculator()

    def place_order(  # type:ignore[override]
        self,
        basket: Basket,
        total: Price,
        shipping_method: BaseShippingMethod,
        shipping_charge: ShippingCharge | Price,
        user: "AbstractBaseUser | None" = None,
        shipping_address: ShippingAddress | None = None,
        billing_address: BillingAddress | None = None,
        order_number: str | None = None,
        status: str | None = None,
        **kwargs: Any,
    ) -> Order:
        # Calculate the tax liability for this shipping address
        if not isinstance(shipping_charge, ShippingCharge):
            shipping_charge = ShippingCharge(
                currency=shipping_charge.currency, excl_tax=shipping_charge.excl_tax
            )
        cch_response = self.get_tax_calculator().apply_taxes(
            shipping_address=shipping_address,
            basket=basket,
            shipping_charge=shipping_charge,
        )
        is_tax_known = cch_response is not None

        # Update order total now that we know taxes
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
        order: Order,
        basket_line: OrderLine,
        extra_line_fields: dict[str, Any] | None = None,
    ) -> OrderLine:
        order_line = super().create_line_models(order, basket_line, extra_line_fields)
        order_line.basket_line = basket_line
        order_line.save()
        return order_line
