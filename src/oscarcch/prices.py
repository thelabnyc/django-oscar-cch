from collections import namedtuple
from decimal import Decimal
from oscar.apps.partner import prices


TaxationDetail = namedtuple(
    'TaxationDetail', ['authority_name', 'tax_name', 'tax_applied', 'fee_applied'])


def _monkey_add_tax(self, authority_name, tax_name, tax_applied='0.00', fee_applied='0.00'):
    tax_applied = Decimal(tax_applied)
    fee_applied = Decimal(fee_applied)

    taxation_detail = TaxationDetail(
        authority_name=authority_name,
        tax_name=tax_name,
        tax_applied=tax_applied,
        fee_applied=fee_applied)
    self.taxation_details.append(taxation_detail)

    if self.tax is None:
        self.tax = Decimal('0.00')
    self.tax += taxation_detail.tax_applied
    self.tax += taxation_detail.fee_applied


def _monkey_clear_taxes(self):
    self.taxation_details = []
    self.tax = None


def monkey_patch_fixed_price():
    """
    MonkeyPatch a few new properties onto oscar.apps.partner.prices.FixedPrice.
    """
    prices.FixedPrice.taxation_details = []
    prices.FixedPrice.add_tax = _monkey_add_tax
    prices.FixedPrice.clear_taxes = _monkey_clear_taxes
