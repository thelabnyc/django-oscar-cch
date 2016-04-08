from decimal import Decimal
from django.db import models, transaction
from django.contrib.postgres.fields import HStoreField
from .settings import CCH_PRECISION


class OrderTaxation(models.Model):
    order = models.OneToOneField('order.Order',
        related_name='taxation',
        on_delete=models.CASCADE,
        primary_key=True)
    transaction_id = models.IntegerField()
    transaction_status = models.IntegerField()
    total_tax_applied = models.DecimalField(decimal_places=2, max_digits=12)
    messages = models.TextField(null=True)

    @classmethod
    def save_details(cls, order, taxes):
        with transaction.atomic():
            order_taxation = cls(order=order)
            order_taxation.transaction_id = taxes.TransactionID
            order_taxation.transaction_status = taxes.TransactionStatus
            order_taxation.total_tax_applied = Decimal(taxes.TotalTaxApplied).quantize(CCH_PRECISION)
            order_taxation.messages = taxes.Messages
            order_taxation.save()

            if taxes.LineItemTaxes:
                for cch_line in taxes.LineItemTaxes.LineItemTax:
                    line = order.lines.get(basket_line__id=cch_line.ID)
                    LineItemTaxation.save_details(line, cch_line)

    def __str__(self):
        return '%s' % (self.transaction_id)


class LineItemTaxation(models.Model):
    line_item = models.OneToOneField('order.Line',
        related_name='taxation',
        on_delete=models.CASCADE)
    country_code = models.CharField(max_length=5)
    state_code = models.CharField(max_length=5)
    total_tax_applied = models.DecimalField(decimal_places=2, max_digits=12)

    @classmethod
    def save_details(cls, line, taxes):
        with transaction.atomic():
            line_taxation = cls(line_item=line)
            line_taxation.country_code = taxes.CountryCode
            line_taxation.state_code = taxes.StateOrProvince
            line_taxation.total_tax_applied = Decimal(taxes.TotalTaxApplied).quantize(CCH_PRECISION)
            line_taxation.save()

            for detail in taxes.TaxDetails.TaxDetail:
                line_detail = LineItemTaxationDetail()
                line_detail.taxation = line_taxation
                line_detail.data = { str(k): str(v) for k, v in dict(detail).items() }
                line_detail.save()

    def __str__(self):
        return '%s: %s' % (self.line_item, self.total_tax_applied)


class LineItemTaxationDetail(models.Model):
    taxation = models.ForeignKey(LineItemTaxation,
        related_name='details',
        on_delete=models.CASCADE)
    data = HStoreField()

    def __str__(self):
        return '%s—%s' % (self.data.get('AuthorityName'), self.data.get('TaxName'))
