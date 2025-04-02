from decimal import Decimal
from typing import NamedTuple

from oscar.apps.partner import prices as app_prices
from oscar.core import prices as core_prices

from . import settings


class TaxationDetail(NamedTuple):
    authority_name: str
    tax_name: str
    tax_applied: Decimal
    fee_applied: Decimal


def _monkey_add_tax(
    self: "_MonkeyPatchedPrice",
    authority_name: str,
    tax_name: str,
    tax_applied: Decimal | str = "0.00",
    fee_applied: Decimal | str = "0.00",
) -> None:
    taxation_detail = TaxationDetail(
        authority_name=authority_name,
        tax_name=tax_name,
        tax_applied=Decimal(tax_applied),
        fee_applied=Decimal(fee_applied),
    )
    self.taxation_details.append(taxation_detail)

    if not self.is_tax_known:
        self.tax = Decimal("0.00")
    self.tax += taxation_detail.tax_applied
    self.tax += taxation_detail.fee_applied


def _monkey_core_clear_taxes(self: "_MonkeyPatchedPrice") -> None:
    self.taxation_details = []
    self.is_tax_known = False
    self.incl_tax = None


def _monkey_app_clear_taxes(self: "_MonkeyPatchedPrice") -> None:
    self.taxation_details = []
    self.tax = None


class _MonkeyPatchedPrice(core_prices.Price):
    taxation_details: list[TaxationDetail] = []
    add_tax = _monkey_add_tax
    clear_taxes = _monkey_core_clear_taxes


def monkey_patch_prices() -> None:
    """
    MonkeyPatch a few new properties onto oscar.apps.partner.prices.FixedPrice.
    """
    core_prices.Price.taxation_details = []  # type:ignore[attr-defined]
    core_prices.Price.add_tax = _monkey_add_tax  # type:ignore[attr-defined]
    core_prices.Price.clear_taxes = (  # type:ignore[attr-defined]
        _monkey_core_clear_taxes
    )

    app_prices.FixedPrice.taxation_details = []  # type:ignore[attr-defined]
    app_prices.FixedPrice.add_tax = _monkey_add_tax  # type:ignore[attr-defined]
    app_prices.FixedPrice.clear_taxes = (  # type:ignore[attr-defined]
        _monkey_app_clear_taxes
    )


class ShippingChargeComponent(_MonkeyPatchedPrice):
    line_id_prefix = "shipping:"

    @classmethod
    def is_cch_shipping_line(cls, cch_line_id: str) -> bool:
        return cch_line_id.startswith(cls.line_id_prefix)

    def __init__(
        self,
        line_id: int,
        currency: str,
        excl_tax: Decimal,
        incl_tax: Decimal | None = None,
        tax: Decimal | None = None,
        cch_sku: str | None = None,
    ) -> None:
        super().__init__(
            currency=currency,
            excl_tax=excl_tax,
            incl_tax=incl_tax,
            tax=tax,
        )
        self._line_id = line_id
        self._cch_sku = cch_sku or settings.CCH_SHIPPING_SKU

    @property
    def cch_line_id(self) -> str:
        return "{prefix}{sku}:{line_id}".format(
            prefix=self.line_id_prefix, sku=self.cch_sku, line_id=self._line_id
        )

    @property
    def cch_sku(self) -> str:
        return self._cch_sku


class ShippingCharge:
    # Code used to store the vat rate reference
    tax_code = None
    components: list[ShippingChargeComponent]

    def __init__(
        self,
        currency: str,
        excl_tax: Decimal | None = None,
        cch_sku: str | None = None,
    ) -> None:
        self.currency = currency
        self.components = []
        if excl_tax is not None:
            self.add_component(cch_sku, excl_tax)

    @property
    def incl_tax(self) -> Decimal:
        return sum([c.incl_tax for c in self.components])

    @property
    def excl_tax(self) -> Decimal:
        return sum([c.excl_tax for c in self.components])

    @property
    def tax(self) -> Decimal:
        return sum([c.tax for c in self.components])

    @property
    def is_tax_known(self) -> bool:
        return (len(self.components) > 0) and all(
            [c.is_tax_known for c in self.components]
        )

    def add_component(self, cch_sku: str | None, charge_excl_tax: Decimal) -> None:
        if self.is_tax_known:
            raise RuntimeError(
                "Can not add new ShippingChargeComponent after tax is already known"
            )
        component = ShippingChargeComponent(
            line_id=len(self.components),
            currency=self.currency,
            excl_tax=charge_excl_tax,
            cch_sku=cch_sku,
        )
        self.components.append(component)

    def __repr__(self) -> str:
        if self.is_tax_known:
            return "{}(currency={!r}, excl_tax={!r}, incl_tax={!r}, tax={!r})".format(
                self.__class__.__name__,
                self.currency,
                self.excl_tax,
                self.incl_tax,
                self.tax,
            )
        return "{}(currency={!r}, excl_tax={!r})".format(
            self.__class__.__name__,
            self.currency,
            self.excl_tax,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ShippingCharge):
            return False
        if len(self.components) != len(other.components):
            return False
        return all([c1 == c2 for c1, c2 in zip(self.components, other.components)])
