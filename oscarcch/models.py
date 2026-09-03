from typing import TYPE_CHECKING

from django.contrib.postgres.fields import HStoreField
from django.db import models, transaction
from zeep.xsd import CompoundValue

from .prices import ShippingChargeComponent
from .settings import CCH_PRECISION
from .types import LineTaxResult, TaxationResult

if TYPE_CHECKING:
    from sandbox.order.models import Line, Order


class OrderTaxation(models.Model):
    """
    Persist top-level taxation data related to an Order.
    """

    #: One-to-one foreign key to :class:`order.Order <oscar.apps.models.Order>`.
    order = models.OneToOneField(
        "order.Order",
        related_name="taxation",
        on_delete=models.CASCADE,
        primary_key=True,
    )

    #: Transaction ID returned by the tax backend
    transaction_id = models.BigIntegerField()

    #: Transaction Status returned by the tax backend
    transaction_status = models.IntegerField()

    #: Total Tax applied to the order
    total_tax_applied = models.DecimalField(decimal_places=2, max_digits=12)

    #: Message text returned by the tax backend
    messages = models.TextField(null=True)

    @classmethod
    def save_details(
        cls, order: "Order", taxes: CompoundValue | TaxationResult
    ) -> None:
        """
        Given an order and a tax calculation result, persist the details.

        :param order: :class:`Order <oscar.apps.order.models.Order>` instance
        :param taxes: Return value of
            :func:`CCHTaxCalculator.apply_taxes <oscarcch.calculator.CCHTaxCalculator.apply_taxes>`
            or :func:`SureTaxCalculator.apply_taxes <oscarcch.suretax.SureTaxCalculator.apply_taxes>`
        """
        if not isinstance(taxes, TaxationResult):
            # Deferred: calculator.py imports Oscar abstract models at module
            # scope, which is unsafe while the app registry is populating
            # (matches order_creator.py). zeep itself is already loaded above.
            from .calculator import cch_response_to_taxation_result

            taxes = cch_response_to_taxation_result(taxes)
        with transaction.atomic():
            order_taxation = cls(order=order)
            order_taxation.transaction_id = taxes.transaction_id
            order_taxation.transaction_status = taxes.transaction_status
            order_taxation.total_tax_applied = taxes.total_tax_applied.quantize(
                CCH_PRECISION
            )
            order_taxation.messages = taxes.messages
            order_taxation.save()
            for line_tax in taxes.line_taxes:
                if ShippingChargeComponent.is_cch_shipping_line(line_tax.line_id):
                    ShippingTaxation.save_details(order, line_tax)
                else:
                    line = order.lines.get(basket_line__id=line_tax.line_id)
                    LineItemTaxation.save_details(line, line_tax)

    def __str__(self) -> str:
        return f"{self.transaction_id}"


class LineItemTaxation(models.Model):
    """
    Persist taxation details related to a single order line.
    """

    #: One-to-one foreign key to :class:`order.Line <oscar.apps.models.Line>`
    line_item = models.OneToOneField(
        "order.Line",
        related_name="taxation",
        on_delete=models.CASCADE,
    )

    #: Country code used to calculate taxes
    country_code = models.CharField(max_length=5)

    #: State code used to calculate taxes
    state_code = models.CharField(max_length=5)

    #: Total tax applied to the line
    total_tax_applied = models.DecimalField(decimal_places=2, max_digits=12)

    @classmethod
    def save_details(cls, line: "Line", taxes: CompoundValue | LineTaxResult) -> None:
        """
        :param taxes: A :class:`LineTaxResult <oscarcch.types.LineTaxResult>`,
            or a ``LineItemTax`` element of a CCH SOAP response.
        """
        if not isinstance(taxes, LineTaxResult):
            from .calculator import cch_line_to_line_tax_result

            taxes = cch_line_to_line_tax_result(taxes)
        with transaction.atomic():
            line_taxation = cls(line_item=line)
            line_taxation.country_code = taxes.country_code
            line_taxation.state_code = taxes.state_code
            line_taxation.total_tax_applied = taxes.total_tax_applied.quantize(
                CCH_PRECISION
            )
            line_taxation.save()
            for detail in taxes.details:
                line_detail = LineItemTaxationDetail()
                line_detail.taxation = line_taxation
                line_detail.data = detail.data
                line_detail.save()

    def __str__(self) -> str:
        return f"{self.line_item}: {self.total_tax_applied}"


class LineItemTaxationDetail(models.Model):
    """
    Represents a single type tax applied to a line.
    """

    #: Many-to-one foreign key to :class:`LineItemTaxation <oscarcch.models.LineItemTaxation>`
    taxation = models.ForeignKey(
        "LineItemTaxation", related_name="details", on_delete=models.CASCADE
    )

    #: HStore of data about the applied tax
    data = HStoreField()

    def __str__(self) -> str:
        return "{}—{}".format(self.data.get("AuthorityName"), self.data.get("TaxName"))


class ShippingTaxation(models.Model):
    """
    Persist taxation details related to an order's shipping charge
    """

    #: Foreign key to :class:`order.Order <oscar.apps.models.Order>`.
    order = models.ForeignKey(
        "order.Order",
        related_name="shipping_taxations",
        on_delete=models.CASCADE,
    )

    #: Line ID sent to CCH to calculate taxes
    cch_line_id = models.CharField(max_length=20)

    #: Country code used to calculate taxes
    country_code = models.CharField(max_length=5)

    #: State code used to calculate taxes
    state_code = models.CharField(max_length=5)

    #: Total tax applied to the line
    total_tax_applied = models.DecimalField(decimal_places=2, max_digits=12)

    class Meta:
        unique_together = (("order", "cch_line_id"),)

    @classmethod
    def save_details(cls, order: "Order", taxes: CompoundValue | LineTaxResult) -> None:
        """
        :param taxes: A :class:`LineTaxResult <oscarcch.types.LineTaxResult>`,
            or a ``LineItemTax`` element of a CCH SOAP response.
        """
        if not isinstance(taxes, LineTaxResult):
            from .calculator import cch_line_to_line_tax_result

            taxes = cch_line_to_line_tax_result(taxes)
        with transaction.atomic():
            shipping_taxation = cls()
            shipping_taxation.order = order
            shipping_taxation.cch_line_id = taxes.line_id
            shipping_taxation.country_code = taxes.country_code
            shipping_taxation.state_code = taxes.state_code
            shipping_taxation.total_tax_applied = taxes.total_tax_applied.quantize(
                CCH_PRECISION
            )
            shipping_taxation.save()
            for detail in taxes.details:
                shipping_detail = ShippingTaxationDetail()
                shipping_detail.taxation = shipping_taxation
                shipping_detail.data = detail.data
                shipping_detail.save()

    def __str__(self) -> str:
        return f"{self.order}: {self.total_tax_applied}"


class ShippingTaxationDetail(models.Model):
    """
    Represents a single type tax applied to a shipping charge
    """

    #: Many-to-one foreign key to :class:`LineItemTaxation <oscarcch.models.LineItemTaxation>`
    taxation = models.ForeignKey(
        "ShippingTaxation", related_name="details", on_delete=models.CASCADE
    )

    #: HStore of data about the applied tax
    data = HStoreField()

    def __str__(self) -> str:
        return "{}—{}".format(self.data.get("AuthorityName"), self.data.get("TaxName"))
