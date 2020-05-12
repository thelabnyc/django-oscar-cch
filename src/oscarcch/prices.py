from collections import namedtuple
from decimal import Decimal
from oscar.core import prices as core_prices
from oscar.apps.partner import prices as app_prices
from . import settings


TaxationDetail = namedtuple(
    'TaxationDetail', ['authority_name', 'tax_name', 'tax_applied', 'fee_applied'])



class ShippingChargeComponent(core_prices.Price):
    line_id_prefix = 'shipping:'

    @classmethod
    def is_cch_shipping_line(cls, cch_line_id):
        return cch_line_id.startswith(cls.line_id_prefix)

    def __init__(self, line_id, currency, excl_tax, incl_tax=None, tax=None, cch_sku=None):
        super().__init__(currency=currency, excl_tax=excl_tax, incl_tax=incl_tax, tax=tax)
        self._line_id = line_id
        self._cch_sku = cch_sku or settings.CCH_SHIPPING_SKU

    @property
    def cch_line_id(self):
        return '{prefix}{sku}:{line_id}'.format(
            prefix=self.line_id_prefix,
            sku=self.cch_sku,
            line_id=self._line_id)

    @property
    def cch_sku(self):
        return self._cch_sku



class ShippingCharge:
    def __init__(self, currency, excl_tax=None, cch_sku=None):
        self.currency = currency
        self.components = []
        if excl_tax is not None:
            self.add_component(cch_sku, excl_tax)

    @property
    def incl_tax(self):
        return sum([c.incl_tax for c in self.components])

    @property
    def excl_tax(self):
        return sum([c.excl_tax for c in self.components])

    @property
    def tax(self):
        return sum([c.tax for c in self.components])

    @property
    def is_tax_known(self):
        return (len(self.components) > 0) and all([c.is_tax_known for c in self.components])

    def add_component(self, cch_sku, charge_excl_tax):
        if self.is_tax_known:
            raise RuntimeError('Can not add new ShippingChargeComponent after tax is already known')
        component = ShippingChargeComponent(
            line_id=len(self.components),
            currency=self.currency,
            excl_tax=charge_excl_tax,
            cch_sku=cch_sku)
        self.components.append(component)

    def __repr__(self):
        if self.is_tax_known:
            return "%s(currency=%r, excl_tax=%r, incl_tax=%r, tax=%r)" % (
                self.__class__.__name__, self.currency, self.excl_tax, self.incl_tax, self.tax)
        return "%s(currency=%r, excl_tax=%r)" % (
            self.__class__.__name__, self.currency, self.excl_tax)

    def __eq__(self, other):
        if len(self.components) != len(other.components):
            return False
        return all([c1 == c2 for c1, c2 in zip(self.components, other.components)])



def _monkey_add_tax(self, authority_name, tax_name, tax_applied='0.00', fee_applied='0.00'):
    tax_applied = Decimal(tax_applied)
    fee_applied = Decimal(fee_applied)

    taxation_detail = TaxationDetail(
        authority_name=authority_name,
        tax_name=tax_name,
        tax_applied=tax_applied,
        fee_applied=fee_applied)
    self.taxation_details.append(taxation_detail)

    if not self.is_tax_known:
        self.tax = Decimal('0.00')
    self.tax += taxation_detail.tax_applied
    self.tax += taxation_detail.fee_applied


def _monkey_core_clear_taxes(self):
    self.taxation_details = []
    self.is_tax_known = False
    self.incl_tax = None


def _monkey_app_clear_taxes(self):
    self.taxation_details = []
    self.tax = None


def monkey_patch_prices():
    """
    MonkeyPatch a few new properties onto oscar.apps.partner.prices.FixedPrice.
    """
    core_prices.Price.taxation_details = []
    core_prices.Price.add_tax = _monkey_add_tax
    core_prices.Price.clear_taxes = _monkey_core_clear_taxes

    app_prices.FixedPrice.taxation_details = []
    app_prices.FixedPrice.add_tax = _monkey_add_tax
    app_prices.FixedPrice.clear_taxes = _monkey_app_clear_taxes
