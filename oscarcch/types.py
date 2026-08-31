from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import NotRequired, TypedDict


@dataclass(frozen=True)
class TaxDetailResult:
    """
    Backend-neutral representation of a single tax applied to a line.

    ``tax_applied`` and ``fee_applied`` are whole-line amounts (inclusive of
    quantity). ``data`` is the complete detail payload persisted to the
    HStore field on the taxation detail models; its keys use the CCH
    vocabulary (``TaxName``, ``AuthorityName``, ``TaxApplied``,
    ``FeeApplied``, ...) regardless of which backend produced it.
    """

    authority_name: str
    tax_name: str
    tax_applied: Decimal
    fee_applied: Decimal
    data: dict[str, str]


@dataclass(frozen=True)
class LineTaxResult:
    """Backend-neutral tax data for a single order/shipping line."""

    line_id: str
    country_code: str
    state_code: str
    total_tax_applied: Decimal
    details: list[TaxDetailResult]


@dataclass(frozen=True)
class TaxationResult:
    """
    Backend-neutral result of a tax calculation.

    Consumed by
    :func:`OrderTaxation.save_details <oscarcch.models.OrderTaxation.save_details>`.
    """

    transaction_id: int
    transaction_status: int
    total_tax_applied: Decimal
    messages: str | None
    line_taxes: list[LineTaxResult]


class CCHAddress(TypedDict):
    Line1: str
    Line2: str
    City: str
    StateOrProvince: str
    PostalCode: str
    Plus4: str | None
    CountryCode: str


class CCHProductInfo(TypedDict):
    ProductGroup: str
    ProductItem: str


class CCHNexusInfo(TypedDict):
    ShipFromAddress: NotRequired[CCHAddress]
    ShipToAddress: NotRequired[CCHAddress]


class CCHLineItem(TypedDict):
    ID: str | int
    AvgUnitPrice: Decimal
    Quantity: int
    ExemptionCode: str | None
    SKU: str
    ProductInfo: NotRequired[CCHProductInfo]
    NexusInfo: CCHNexusInfo


class CCHLineItems(TypedDict):
    LineItem: list[CCHLineItem]


class CCHOrder(TypedDict):
    InvoiceDate: datetime
    SourceSystem: str
    TestTransaction: bool
    TransactionType: str
    CustomerType: str
    ProviderType: str
    TransactionID: int
    finalize: bool
    LineItems: CCHLineItems
