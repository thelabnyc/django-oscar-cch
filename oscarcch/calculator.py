from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
import logging

from django.utils.functional import cached_property
from zeep.transports import Transport
from zeep.xsd import CompoundValue
import zeep
import zeep.cache

from . import exceptions, settings, types

if TYPE_CHECKING:
    from oscar.apps.basket.models import Basket
    from oscar.apps.basket.models import Line as BasketLine
    from oscar.apps.order.models import ShippingAddress
    from oscar.apps.partner.models import PartnerAddress
    import pybreaker

    from .prices import ShippingCharge, _MonkeyPatchedPrice


logger = logging.getLogger(__name__)

POSTCODE_LEN = 5
PLUS4_LEN = 4


class CCHTaxCalculator:
    """
    Simple interface between Python and the CCH Sales Tax Office SOAP API.
    """

    precision = settings.CCH_PRECISION
    wsdl = settings.CCH_WSDL
    proxy_url = settings.CCH_PROXY_URL
    open_timeout = settings.CCH_OPEN_TIMEOUT
    send_timeout = settings.CCH_SEND_TIMEOUT
    entity_id = settings.CCH_ENTITY
    divsion_id = settings.CCH_DIVISION
    max_retries = settings.CCH_MAX_RETRIES

    def __init__(self, breaker: "pybreaker.CircuitBreaker | None" = None):
        """
        Construct a CCHTaxCalculator instance

        You may optionally supply a ``pybreaker.CircuitBreaker`` instance. If you do so, it will be used to
        implement the CircuitBreaker pattern around the SOAP calls to the CCH web service.

        :param breaker: Optional :class:`CircuitBreaker <pybreaker.CircuitBreaker>` instance
        """
        self.breaker = breaker

    @property
    def client_settings(self) -> zeep.Settings:
        settings = zeep.Settings()
        return settings

    @cached_property
    def client(self) -> zeep.Client:
        """
        Construct and return a zeep SOAP client
        """
        wsdl_cache = zeep.cache.InMemoryCache()
        transport = Transport(
            cache=wsdl_cache,
            timeout=self.open_timeout,
            operation_timeout=self.send_timeout,
        )
        if self.proxy_url:
            proxies = {
                "http": self.proxy_url,
                "https": self.proxy_url,
            }
            transport.session.proxies.update(proxies)
        client = zeep.Client(
            wsdl=self.wsdl,
            settings=self.client_settings,
            transport=transport,
        )
        return client

    def apply_taxes(
        self,
        shipping_address: "ShippingAddress | None",
        basket: "Basket | None" = None,
        shipping_charge: "ShippingCharge | None" = None,
    ) -> CompoundValue | None:
        """
        Apply taxes to a Basket instance using the given shipping address.

        Pass return value of this method to :func:`OrderTaxation.save_details <oscarcch.models.OrderTaxation.save_details>`
        to persist the taxation details, CCH transaction ID, etc in the database.

        :param shipping_address: :class:`ShippingAddress <oscar.apps.order.models.ShippingAddress>` instance
        :param basket: :class:`Basket <oscar.apps.basket.models.Basket>` instance
        :param shipping_charge: :class:`ShippingCharge <oscarcch.prices.ShippingCharge>` instance
        :return: SOAP Response.
        """
        response: CompoundValue | None = self._get_response(
            shipping_address, basket, shipping_charge
        )

        # Check the response for errors
        respOK = self._check_response_messages(response)
        if not respOK:
            response = None

        # Build map of line IDs to line tax details
        cch_line_map: dict[str, CompoundValue] = {}
        if response and response.LineItemTaxes:
            cch_line_map = {
                item.ID: item for item in response.LineItemTaxes.LineItemTax
            }

        # Apply taxes to line items
        if basket is not None:
            for line in basket.all_lines():
                line_id = str(line.id)
                taxes = cch_line_map.get(line_id)
                self._apply_taxes_to_price(
                    taxes,
                    line.purchase_info.price,
                    line.quantity,
                )

        # Apply taxes to shipping charge
        if shipping_charge is not None:
            for shipping_charge_component in shipping_charge.components:
                shipping_taxes = cch_line_map.get(shipping_charge_component.cch_line_id)
                self._apply_taxes_to_price(shipping_taxes, shipping_charge_component, 1)

        # Return CCH response
        return response

    def _apply_taxes_to_price(
        self,
        taxes: CompoundValue | None,
        price: "_MonkeyPatchedPrice",
        quantity: int,
    ) -> None:
        # Taxes come in two forms: quantity and percentage based
        # We need to handle both of those here. The tricky part is that CCH returns data
        # for an entire line item (inclusive quantity), but Oscar needs the tax info for
        # each unit in the line (exclusive quantity). So, we use the details provided to
        # derive the per-unit taxes before applying them.
        price.clear_taxes()
        if taxes:
            for tax in taxes.TaxDetails.TaxDetail:
                unit_fee = Decimal(str(tax.FeeApplied)) / quantity
                unit_tax = Decimal(str(tax.TaxApplied)) / quantity
                price.add_tax(
                    authority_name=tax.AuthorityName,
                    tax_name=tax.TaxName,
                    tax_applied=unit_tax,
                    fee_applied=unit_fee,
                )
            # Check our work and make sure the total we arrived at matches the total CCH gave us
            total_line_tax = (price.tax * quantity).quantize(self.precision)
            total_applied_tax = Decimal(taxes.TotalTaxApplied).quantize(self.precision)
            if total_applied_tax != total_line_tax:
                raise RuntimeError(
                    (
                        "Taxation miscalculation occurred! "
                        "Details sum to %s, which doesn't match given sum of %s"
                    )
                    % (total_line_tax, taxes.TotalTaxApplied)
                )
        else:
            price.tax = Decimal("0.00")

    def _get_response(
        self,
        shipping_address: "ShippingAddress | None",
        basket: "Basket | None",
        shipping_charge: "ShippingCharge | None",
    ) -> CompoundValue | None:
        """Fetch CCH tax data for the given basket and shipping address"""
        response = None
        retry_count = 0
        while response is None and retry_count <= self.max_retries:
            response = self._get_response_inner(
                shipping_address, basket, shipping_charge, retry_count=retry_count
            )
            retry_count += 1
        return response

    def _get_response_inner(
        self,
        shipping_address: "ShippingAddress | None",
        basket: "Basket | None",
        shipping_charge: "ShippingCharge | None",
        retry_count: int,
    ) -> CompoundValue | None:
        response = None

        def _call_service() -> CompoundValue | None:
            order = self._build_order(shipping_address, basket, shipping_charge)
            if order is None:
                return None
            response = self.client.service.CalculateRequest(
                self.entity_id,
                self.divsion_id,
                order,
            )
            return response

        try:
            if self.breaker is not None:
                response = self.breaker.call(_call_service)
            else:
                response = _call_service()
        except Exception as e:
            logger.exception(e)
        return response

    def _check_response_messages(self, response: CompoundValue | None) -> bool:
        """Raise an exception if response messages contains any reported errors."""
        if response is None:
            return False
        if response.Messages:
            for message in response.Messages.Message:
                if message.Code > 0:
                    exc = exceptions.build(message.Severity, message.Code, message.Info)
                    logger.exception(exc)
                    return False
        return True

    def _build_order(
        self,
        shipping_address: "ShippingAddress | None",
        basket: "Basket | None",
        shipping_charge: "ShippingCharge | None",
    ) -> types.CCHOrder | None:
        """Convert an Oscar Basket and ShippingAddresss into a CCH Order object"""
        order = types.CCHOrder(
            InvoiceDate=datetime.now(settings.CCH_TIME_ZONE),
            SourceSystem=settings.CCH_SOURCE_SYSTEM,
            TestTransaction=settings.CCH_TEST_TRANSACTIONS,
            TransactionType=settings.CCH_TRANSACTION_TYPE,
            CustomerType=settings.CCH_CUSTOMER_TYPE,
            ProviderType=settings.CCH_PROVIDER_TYPE,
            TransactionID=0,
            finalize=settings.CCH_FINALIZE_TRANSACTION,
            LineItems=types.CCHLineItems(
                LineItem=[],
            ),
        )

        # Add CCH lines for each basket line
        if basket is not None:
            for line in basket.all_lines():
                qty = getattr(line, "cch_quantity", line.quantity)
                if qty <= 0:
                    continue
                # Line Info
                item = types.CCHLineItem(
                    ID=line.id,
                    AvgUnitPrice=Decimal(
                        line.line_price_excl_tax_incl_discounts / qty
                    ).quantize(Decimal("0.00001")),
                    Quantity=qty,
                    ExemptionCode=None,
                    SKU=self._get_product_data("sku", line),
                    # Product Info
                    ProductInfo=types.CCHProductInfo(
                        ProductGroup=self._get_product_data("group", line),
                        ProductItem=self._get_product_data("item", line),
                    ),
                    # Ship From/To Addresses
                    NexusInfo=types.CCHNexusInfo(),
                )
                if shipping_address is not None:
                    item["NexusInfo"]["ShipToAddress"] = self._build_address(
                        shipping_address
                    )
                warehouse = line.stockrecord.partner.primary_address
                if warehouse:
                    item["NexusInfo"]["ShipFromAddress"] = self._build_address(
                        warehouse
                    )
                # Add line to order
                order["LineItems"]["LineItem"].append(item)

        # Add CCH lines for shipping charges
        if shipping_charge is not None and settings.CCH_SHIPPING_TAXES_ENABLED:
            for shipping_charge_component in shipping_charge.components:
                shipping_line = types.CCHLineItem(
                    ID=shipping_charge_component.cch_line_id,
                    AvgUnitPrice=shipping_charge_component.excl_tax.quantize(
                        Decimal("0.00001")
                    ),
                    Quantity=1,
                    ExemptionCode=None,
                    SKU=shipping_charge_component.cch_sku,
                    NexusInfo=types.CCHNexusInfo(),
                )
                if shipping_address is not None:
                    shipping_line["NexusInfo"]["ShipToAddress"] = self._build_address(
                        shipping_address
                    )
                # Add shipping line to order
                order["LineItems"]["LineItem"].append(shipping_line)

        # Must include at least 1 line item
        if len(order["LineItems"]["LineItem"]) <= 0:
            return None

        # Return order
        return order

    def _build_address(
        self,
        oscar_address: "ShippingAddress | PartnerAddress",
    ) -> types.CCHAddress:
        postcode, plus4 = self.format_postcode(oscar_address.postcode)
        addr = types.CCHAddress(
            Line1=oscar_address.line1,
            Line2=oscar_address.line2,
            City=oscar_address.city,
            StateOrProvince=oscar_address.state,
            PostalCode=postcode,
            Plus4=plus4,
            CountryCode=oscar_address.country.code,
        )
        return addr

    def _get_product_data(
        self,
        key: str,
        line: "BasketLine",
    ) -> str:
        key = "cch_product_%s" % key
        sku = getattr(settings, key.upper())
        sku = getattr(line.product.attr, key.lower(), sku)
        return sku

    def format_postcode(self, raw_postcode: str) -> tuple[str, str | None]:
        if not raw_postcode:
            return "", ""
        postcode, plus4 = raw_postcode[:POSTCODE_LEN], None
        # Set Plus4 if PostalCode provided as 9 digits separated by hyphen
        if len(raw_postcode) == POSTCODE_LEN + PLUS4_LEN + 1:
            plus4 = raw_postcode[POSTCODE_LEN + 1 :]
        return postcode, plus4
