from decimal import Decimal
from typing import TYPE_CHECKING
import json

from django.contrib.postgres.fields import HStoreField
from django.db import models, transaction
from zeep.xsd import CompoundValue
import zeep.helpers

from .prices import ShippingChargeComponent
from .settings import CCH_PRECISION

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

    #: Transaction ID returned by CCH
    transaction_id = models.IntegerField()

    #: Transaction Status returned by CCH
    transaction_status = models.IntegerField()

    #: Total Tax applied to the order
    total_tax_applied = models.DecimalField(decimal_places=2, max_digits=12)

    #: Message text returned by CCH
    messages = models.TextField(null=True)

    @classmethod
    def save_details(cls, order: "Order", taxes: CompoundValue) -> None:
        """
        Given an order and a SOAP response, persist the details.

        :param order: :class:`Order <oscar.apps.order.models.Order>` instance
        :param taxes: Return value of :func:`CCHTaxCalculator.apply_taxes <oscarcch.calculator.CCHTaxCalculator.apply_taxes>`
        """
        with transaction.atomic():
            order_taxation = cls(order=order)
            order_taxation.transaction_id = taxes.TransactionID
            order_taxation.transaction_status = taxes.TransactionStatus
            order_taxation.total_tax_applied = Decimal(taxes.TotalTaxApplied).quantize(
                CCH_PRECISION
            )
            order_taxation.messages = (
                json.dumps(
                    zeep.helpers.serialize_object(taxes.Messages.Message), indent=4
                )
                if len(taxes.Messages.Message) > 0
                else None
            )
            order_taxation.save()
            if taxes.LineItemTaxes:
                for cch_line in taxes.LineItemTaxes.LineItemTax:
                    if ShippingChargeComponent.is_cch_shipping_line(cch_line.ID):
                        ShippingTaxation.save_details(order, cch_line)
                    else:
                        line = order.lines.get(basket_line__id=cch_line.ID)
                        LineItemTaxation.save_details(line, cch_line)

    def __str__(self) -> str:
        return "%s" % (self.transaction_id)


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
    def save_details(cls, line: "Line", taxes: CompoundValue) -> None:
        with transaction.atomic():
            line_taxation = cls(line_item=line)
            line_taxation.country_code = taxes.CountryCode
            line_taxation.state_code = taxes.StateOrProvince
            line_taxation.total_tax_applied = Decimal(taxes.TotalTaxApplied).quantize(
                CCH_PRECISION
            )
            line_taxation.save()
            for detail in taxes.TaxDetails.TaxDetail:
                line_detail = LineItemTaxationDetail()
                line_detail.taxation = line_taxation
                line_detail.data = {
                    str(k): str(v)
                    for k, v in zeep.helpers.serialize_object(detail).items()
                }
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
        unique_together = [
            ("order", "cch_line_id"),
        ]

    @classmethod
    def save_details(cls, order: "Order", taxes: CompoundValue) -> None:
        with transaction.atomic():
            shipping_taxation = cls()
            shipping_taxation.order = order
            shipping_taxation.cch_line_id = taxes.ID
            shipping_taxation.country_code = taxes.CountryCode
            shipping_taxation.state_code = taxes.StateOrProvince
            shipping_taxation.total_tax_applied = Decimal(
                taxes.TotalTaxApplied
            ).quantize(CCH_PRECISION)
            shipping_taxation.save()
            for detail in taxes.TaxDetails.TaxDetail:
                shipping_detail = ShippingTaxationDetail()
                shipping_detail.taxation = shipping_taxation
                shipping_detail.data = {
                    str(k): str(v)
                    for k, v in zeep.helpers.serialize_object(detail).items()
                }
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
