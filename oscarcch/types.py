from datetime import datetime
from decimal import Decimal
from typing import NotRequired, TypedDict


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
