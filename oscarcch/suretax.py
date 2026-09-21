from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
import json
import logging
import re
import time

from django.core.exceptions import ImproperlyConfigured
from django.utils.functional import cached_property
import requests

from . import exceptions, settings
from .prices import TaxablePrice
from .types import LineTaxResult, TaxationResult, TaxDetailResult

if TYPE_CHECKING:
    from oscar.apps.basket.models import Basket
    from oscar.apps.order.models import ShippingAddress
    from oscar.apps.partner.models import PartnerAddress
    import pybreaker

    from .prices import ShippingCharge


logger = logging.getLogger(__name__)

ZIP_RE = re.compile(r"^(\d{5})(?:-?(\d{4}))?$")

#: Header ResponseCode indicating full success
RESPONSE_CODE_SUCCESS = "9999"
#: Header ResponseCode indicating per-item validation errors
RESPONSE_CODE_ITEM_ERRORS = "9001"
#: Item ResponseCodes meaning SureTax could not resolve the ship-to address
#: to a jurisdiction. These are bad shopper input, not integration bugs; CCH
#: STO returned zero tax for such addresses without reporting anything.
ADDRESS_ERROR_CODES = frozenset({"9120", "9151", "9400"})

#: TaxSitusRule: use all addresses to determine situs
SITUS_RULE_ALL_ADDRESSES = "22"
#: TaxSitusRule: use only the ship-to address to determine situs
SITUS_RULE_SHIP_TO = "23"

#: HTTP statuses retried as transient infrastructure failures. 403 is the WAF
#: rate-limit/size block in front of the API, not an application response.
RETRY_STATUSES = (403, 408, 429, 500, 502, 503, 504)

#: Exponential backoff base between retries (seconds); no sleep before the first retry.
RETRY_BACKOFF_FACTOR = 0.5


def _decimal(value: Any) -> Decimal:
    """Parse a SureTax numeric field, reading JSON null as zero."""
    return Decimal(str(value or 0))


def _text(value: Any) -> str:
    """Parse a SureTax text field destined for the database, which cannot hold NUL."""
    text = "" if value is None else str(value)
    if "\x00" in text:
        raise exceptions.SureTaxError("", "NUL character in SureTax response text")
    return text


def _is_address_error(exc: exceptions.SureTaxError) -> bool:
    """Did every item of a 9001 response fail only on address resolution?"""
    return bool(exc.item_messages) and all(
        str(message.get("ResponseCode")) in ADDRESS_ERROR_CODES
        for message in exc.item_messages
    )


def _is_transient(exc: requests.RequestException) -> bool:
    """Connection and timeout errors, plus the HTTP statuses in RETRY_STATUSES."""
    if isinstance(exc, requests.HTTPError):
        return exc.response is not None and exc.response.status_code in RETRY_STATUSES
    return True


class SureTaxCalculator:
    """
    Interface between Python and the CCH SureTax General Merchandise API.

    Exposes the same public surface as
    :class:`CCHTaxCalculator <oscarcch.calculator.CCHTaxCalculator>`, but
    returns a backend-neutral
    :class:`TaxationResult <oscarcch.types.TaxationResult>` instead of a SOAP
    response object.

    Calculations are quote-only (``ReturnFileCode: "Q"``): nothing is recorded
    on the SureTax side for compliance reporting.
    """

    precision = settings.CCH_PRECISION
    base_url = settings.SURETAX_API_BASE_URL
    client_number = settings.SURETAX_CLIENT_NUMBER
    validation_key = settings.SURETAX_VALIDATION_KEY
    business_unit = settings.SURETAX_BUSINESS_UNIT
    client_tracking = settings.SURETAX_CLIENT_TRACKING
    timeout = settings.SURETAX_TIMEOUT
    max_retries = settings.SURETAX_MAX_RETRIES
    tax_name_map = settings.SURETAX_TAX_NAME_MAP

    def __init__(self, breaker: pybreaker.CircuitBreaker | None = None):
        """
        Construct a SureTaxCalculator instance

        You may optionally supply a ``pybreaker.CircuitBreaker`` instance. If you do so, it will be used to
        implement the CircuitBreaker pattern around the HTTP calls to the SureTax web service. Errors that
        SureTax reports in the response body (bad item data, header errors) are classified outside the
        breaker and never count as service failures.

        Each transport attempt (up to ``SURETAX_MAX_RETRIES`` retries) is a separate breaker call, so
        every failed attempt counts as one failure and the breaker is held for one request at a time,
        as with :class:`CCHTaxCalculator <oscarcch.calculator.CCHTaxCalculator>`.

        :param breaker: Optional :class:`CircuitBreaker <pybreaker.CircuitBreaker>` instance
        """
        if not self.base_url or not self.client_number or not self.validation_key:
            raise ImproperlyConfigured(
                "SURETAX_API_BASE_URL, SURETAX_CLIENT_NUMBER, and "
                "SURETAX_VALIDATION_KEY must be set to use SureTaxCalculator"
            )
        self.breaker = breaker

    @property
    def endpoint(self) -> str:
        return f"{self.base_url.rstrip('/')}/Services/V07/SureTax.asmx/PostRequest"

    def apply_taxes(
        self,
        shipping_address: ShippingAddress | None,
        basket: Basket | None = None,
        shipping_charge: ShippingCharge | None = None,
    ) -> TaxationResult | None:
        """
        Apply taxes to a Basket instance using the given shipping address.

        Pass return value of this method to :func:`OrderTaxation.save_details <oscarcch.models.OrderTaxation.save_details>`
        to persist the taxation details, SureTax transaction ID, etc in the database.

        :param shipping_address: :class:`ShippingAddress <oscar.apps.order.models.ShippingAddress>` instance
        :param basket: :class:`Basket <oscar.apps.basket.models.Basket>` instance
        :param shipping_charge: :class:`ShippingCharge <oscarcch.prices.ShippingCharge>` instance
        :return: :class:`TaxationResult <oscarcch.types.TaxationResult>`, or None if tax is unknown.
        """
        result = self._get_response(shipping_address, basket, shipping_charge)

        # Build map of line IDs to line tax details
        line_map: dict[str, LineTaxResult] = {}
        if result is not None:
            line_map = {line_tax.line_id: line_tax for line_tax in result.line_taxes}

        # Apply taxes to line items
        if basket is not None:
            self._apply_taxes_to_basket(basket, line_map)

        # Apply taxes to shipping charge
        if shipping_charge is not None:
            for shipping_charge_component in shipping_charge.components:
                shipping_taxes = line_map.get(shipping_charge_component.cch_line_id)
                self._apply_taxes_to_price(shipping_taxes, shipping_charge_component, 1)

        return result

    def _apply_taxes_to_basket(
        self,
        basket: Basket,
        line_map: dict[str, LineTaxResult],
    ) -> None:
        """Apply tax data from the SureTax response to each basket line's price.

        Override in subclasses to customize which lines receive tax data.
        """
        for line in basket.all_lines():
            line_taxes = line_map.get(str(line.id))
            price = line.purchase_info.price
            if isinstance(price, TaxablePrice):
                self._apply_taxes_to_price(line_taxes, price, line.quantity)

    def _apply_taxes_to_price(
        self,
        line_taxes: LineTaxResult | None,
        price: TaxablePrice,
        quantity: int,
    ) -> None:
        # SureTax returns tax amounts for an entire line item (inclusive
        # quantity), but Oscar needs the tax info for each unit in the line
        # (exclusive quantity), so divide the amounts by the line quantity.
        price.clear_taxes()
        if line_taxes and line_taxes.details:
            for detail in line_taxes.details:
                price.add_tax(
                    authority_name=detail.authority_name,
                    tax_name=detail.tax_name,
                    tax_applied=detail.tax_applied / quantity,
                    fee_applied=detail.fee_applied / quantity,
                )
        else:
            price.tax = Decimal("0.00")

    def _get_response(
        self,
        shipping_address: ShippingAddress | None,
        basket: Basket | None,
        shipping_charge: ShippingCharge | None,
    ) -> TaxationResult | None:
        """
        Fetch SureTax tax data for the given basket and shipping address.

        Any failure (transport, SureTax-reported error, malformed response)
        degrades to ``None`` so checkout proceeds tax-unknown. Only the HTTP
        call runs inside the breaker; body errors never count as outages.
        """
        try:
            payload = self._build_request_payload(
                shipping_address, basket, shipping_charge
            )
            if payload is None:
                return None
            body = self._post_with_retries(payload)
            return self._parse_response(body, payload, shipping_address)
        except exceptions.SureTaxError as e:
            if _is_address_error(e):
                logger.warning("SureTax could not resolve the ship-to address: %s", e)
            else:
                logger.exception("Failed to fetch SureTax tax data")
            return None
        except Exception:
            logger.exception("Failed to fetch SureTax tax data")
            return None

    def _post_with_retries(self, payload: dict[str, Any]) -> str:
        """
        POST the payload, retrying transient transport failures.

        Each attempt is its own breaker call: pybreaker holds a lock for the
        whole of ``call``, so wrapping the retry loop instead would block every
        checkout sharing the breaker for the full backoff window.
        """
        # Retrying the POST is safe only because requests are quote-only
        # (ReturnFileCode "Q" in _build_request_payload): a replayed request
        # records nothing on the SureTax side.
        attempt = 0
        while True:
            try:
                if self.breaker is not None:
                    return self.breaker.call(self._post, payload)
                return self._post(payload)
            except requests.RequestException as e:
                if attempt >= self.max_retries or not _is_transient(e):
                    raise
            # A vendor Retry-After is deliberately not honoured: it could park
            # a checkout worker well past SURETAX_TIMEOUT.
            if attempt:
                time.sleep(RETRY_BACKOFF_FACTOR * 2**attempt)
            attempt += 1

    @cached_property
    def session(self) -> requests.Session:
        """HTTP session for this instance. Connections are pooled across calls
        only if the integrator reuses the calculator instance; the default
        ``get_tax_calculator`` builds a new one per order."""
        return requests.Session()

    def _post(self, payload: dict[str, Any]) -> str:
        """POST the payload and return the raw response body.

        Everything here is transport and runs inside the circuit breaker;
        interpreting the body, JSON decoding included, belongs to
        :meth:`_parse_response` so body problems never count as outages.
        """
        # The serialized body (credentials included) is a named argument in the
        # requests/urllib3 frames, so a transport failure's traceback carries it
        # in frame locals that Sentry captures. Re-raise from this frame with
        # the chain suppressed so those frames are never part of the report,
        # keeping the concrete class so breaker exclude lists and Sentry
        # grouping can still tell a config fault from an outage.
        try:
            response = self.session.post(
                self.endpoint,
                json={
                    "request": json.dumps(
                        {
                            "ClientNumber": self.client_number,
                            "ValidationKey": self.validation_key,
                            "BusinessUnit": self.business_unit,
                            **payload,
                        }
                    )
                },
                timeout=self.timeout,
                # Credentials ride in the body; never replay them to a redirect target.
                allow_redirects=False,
            )
            response.raise_for_status()
            if response.is_redirect:
                # allow_redirects=False hands a 3xx back as a "success" whose
                # body is not a SureTax envelope; treat it as a transport error.
                raise requests.HTTPError(
                    f"Unexpected redirect ({response.status_code})", response=response
                )
        except requests.RequestException as e:
            # The response is kept (an attribute, not a frame local) so the
            # retry loop can classify HTTP statuses.
            raise type(e)(f"SureTax request failed: {e}", response=e.response) from None
        return response.text

    def _unwrap_response(self, body: str) -> dict[str, Any]:
        """Decode the ASMX envelope and raise for any SureTax-reported error."""
        # The ASMX endpoint wraps the real response as a JSON string under "d".
        wrapper = json.loads(body)
        envelope = wrapper.get("d") if isinstance(wrapper, dict) else None
        if not isinstance(envelope, str):
            raise exceptions.SureTaxError(
                "", "Unexpected SureTax response: missing 'd' envelope"
            )
        data: dict[str, Any] = json.loads(envelope)
        response_code = str(data.get("ResponseCode", ""))
        if data.get("Successful") != "Y" or response_code not in (
            RESPONSE_CODE_SUCCESS,
            RESPONSE_CODE_ITEM_ERRORS,
        ):
            raise exceptions.SureTaxError(
                response_code, str(data.get("HeaderMessage", ""))
            )
        if response_code == RESPONSE_CODE_ITEM_ERRORS:
            item_messages = data.get("ItemMessages") or []
            raise exceptions.SureTaxError(
                response_code, json.dumps(item_messages), item_messages
            )
        return data

    def _parse_response(
        self,
        body: str,
        payload: dict[str, Any],
        shipping_address: ShippingAddress | None,
    ) -> TaxationResult:
        data = self._unwrap_response(body)
        response_code = str(data["ResponseCode"])

        # Group tax details by submitted line number
        submitted_units = {
            item["LineNumber"]: Decimal(item["Units"]) for item in payload["ItemList"]
        }
        grouped_details: dict[str, list[TaxDetailResult]] = {}
        state_codes: dict[str, str] = {}
        for group in data.get("GroupList") or []:
            line_id = str(group.get("LineNumber"))
            if line_id not in submitted_units:
                raise exceptions.SureTaxError(
                    response_code,
                    f"Response contains unknown line number: {line_id}",
                )
            details = grouped_details.setdefault(line_id, [])
            state_codes.setdefault(line_id, _text(group.get("StateCode") or ""))
            for tax in group.get("TaxList") or []:
                details.append(self._build_tax_detail(tax, submitted_units[line_id]))

        # Lines with no tax are omitted from GroupList entirely (as CCH STO
        # omits them from LineItemTaxes); they are applied as zero tax.
        # The response contains no country data; fill it in from the shipping address.
        country_code = (
            shipping_address.country.code if shipping_address is not None else ""
        )
        line_taxes = [
            LineTaxResult(
                line_id=line_id,
                country_code=country_code,
                state_code=state_codes[line_id],
                total_tax_applied=sum(
                    (detail.tax_applied + detail.fee_applied for detail in details),
                    Decimal(0),
                ),
                details=details,
            )
            for line_id, details in grouped_details.items()
        ]

        # Check our work and make sure the details sum to the total SureTax gave us
        total_tax = _decimal(data["TotalTax"])
        details_total = sum((lt.total_tax_applied for lt in line_taxes), Decimal(0))
        if details_total.quantize(self.precision) != total_tax.quantize(self.precision):
            raise exceptions.SureTaxError(
                response_code,
                "Taxation miscalculation occurred! "
                f"Details sum to {details_total}, which doesn't match "
                f"given sum of {total_tax}",
            )
        # OrderTaxation.transaction_id is a bigint; an out-of-range value would
        # otherwise surface as a DataError inside the order transaction.
        transaction_id = int(data["TransId"])
        if not 0 <= transaction_id < 2**63:
            raise exceptions.SureTaxError(
                response_code, f"TransId out of range: {transaction_id}"
            )
        return TaxationResult(
            backend="suretax",
            transaction_id=transaction_id,
            transaction_status=int(response_code),
            total_tax_applied=total_tax,
            # A successful HeaderMessage is the constant "Success" and item
            # messages already raised SureTaxError, so there is nothing
            # left worth persisting (CCH stores warnings here, or None).
            messages=None,
            line_taxes=line_taxes,
        )

    def _build_tax_detail(self, tax: dict[str, Any], units: Decimal) -> TaxDetailResult:
        amount = _decimal(tax.get("TaxAmount"))
        if amount < 0:
            # A sales quote never credits the customer; a negative amount would
            # otherwise flow through reconciliation and apply as a discount.
            raise exceptions.SureTaxError(
                "", f"Negative TaxAmount in quote response: {amount}"
            )
        # Discriminate unit-based fees (e.g. recycling fees) from percentage
        # taxes: per the API docs, FeeRate is non-zero for fees.
        is_fee = _decimal(tax.get("FeeRate")) > 0
        revenue = _decimal(tax.get("Revenue"))
        # RevenueBase is back-computed from the rounded tax amount and can
        # exceed Revenue; PercentTaxable is the authoritative taxable share.
        percent_taxable = tax.get("PercentTaxable")
        taxable_amount = (
            revenue
            if percent_taxable is None
            else (revenue * Decimal(str(percent_taxable))).quantize(self.precision)
        )
        tax_name = _text(tax.get("TaxTypeDesc") or "")
        tax_name = self.tax_name_map.get(tax_name, tax_name)
        authority_name = _text(tax.get("TaxAuthorityName") or "")
        tax_applied = Decimal(0) if is_fee else amount
        fee_applied = amount if is_fee else Decimal(0)
        # FeeRate is already scaled by the submitted Units, so the taxable
        # quantity of a fee is the units sent, not TaxAmount / FeeRate.
        taxable_quantity = units if is_fee else Decimal(0)
        # Persist the native SureTax fields, plus the CCH key vocabulary that
        # downstream consumers of the HStore data match on.
        data = {_text(k): _text(v) for k, v in tax.items()}
        data.update(
            {
                "TaxName": tax_name,
                "AuthorityName": authority_name,
                "TaxApplied": str(tax_applied),
                "FeeApplied": str(fee_applied),
                "TaxableAmount": str(taxable_amount),
                "ExemptAmt": str(revenue - taxable_amount),
                "TaxableQuantity": str(taxable_quantity),
                "ExemptQty": "0",
            }
        )
        return TaxDetailResult(
            authority_name=authority_name,
            tax_name=tax_name,
            tax_applied=tax_applied,
            fee_applied=fee_applied,
            data=data,
        )

    def _build_request_payload(
        self,
        shipping_address: ShippingAddress | None,
        basket: Basket | None,
        shipping_charge: ShippingCharge | None,
    ) -> dict[str, Any] | None:
        """Convert an Oscar Basket and ShippingAddress into a SureTax request payload"""
        now = datetime.now(settings.CCH_TIME_ZONE)
        ship_to = (
            self._build_address(shipping_address)
            if shipping_address is not None
            else None
        )

        def build_item(
            line_number: str, revenue: Decimal, units: int, sku: str
        ) -> dict[str, Any]:
            item: dict[str, Any] = {
                "LineNumber": line_number,
                "TransDate": f"{now:%m/%d/%Y}",
                "Revenue": str(revenue.quantize(self.precision)),
                "Units": str(units),
                "TaxIncludedCode": "0",
                "TaxSitusRule": SITUS_RULE_SHIP_TO,
                "TransTypeCode": sku,
                "SalesTypeCode": "T",
                "RegulatoryCode": "70",
            }
            if ship_to is not None:
                item["ShipToAddress"] = ship_to
            return item

        items: list[dict[str, Any]] = []
        if basket is not None:
            for line in basket.all_lines():
                qty = getattr(line, "cch_quantity", line.quantity)
                # Line tax is divided by line.quantity when applied, so a
                # zero-quantity line is never sent, override or not.
                if qty <= 0 or line.quantity <= 0:
                    continue
                line_price = line.line_price_excl_tax_incl_discounts
                assert line_price is not None
                # Option-type attributes yield an AttributeOption, which the CCH
                # SOAP client stringifies but json.dumps rejects.
                sku = str(
                    getattr(
                        line.product.attr, "cch_product_sku", settings.CCH_PRODUCT_SKU
                    )
                )
                item = build_item(str(line.id), Decimal(line_price), qty, sku)
                warehouse = line.stockrecord.partner.primary_address
                if warehouse:
                    item["ShipFromAddress"] = self._build_address(warehouse)
                    item["TaxSitusRule"] = SITUS_RULE_ALL_ADDRESSES
                items.append(item)

        if shipping_charge is not None and settings.CCH_SHIPPING_TAXES_ENABLED:
            items.extend(
                build_item(c.cch_line_id, c.excl_tax, 1, c.cch_sku)
                for c in shipping_charge.components
            )

        # Must include at least 1 item
        if not items:
            return None

        total_revenue = sum((Decimal(item["Revenue"]) for item in items), Decimal(0))
        return {
            "DataYear": f"{now:%Y}",
            "DataMonth": f"{now:%m}",
            "CmplDataYear": f"{now:%Y}",
            "CmplDataMonth": f"{now:%m}",
            "TotalRevenue": str(total_revenue),
            "ReturnFileCode": "Q",
            "ClientTracking": self.client_tracking,
            "ResponseType": "D2",
            "ResponseGroup": "00",
            "STAN": "",
            "ItemList": items,
        }

    def _build_address(
        self,
        oscar_address: ShippingAddress | PartnerAddress,
    ) -> dict[str, str]:
        postcode, plus4 = self.format_postcode(oscar_address.postcode)
        return {
            "PrimaryAddressLine": oscar_address.line1,
            "SecondaryAddressLine": oscar_address.line2,
            "City": oscar_address.city,
            "State": oscar_address.state,
            "PostalCode": postcode,
            "Plus4": plus4,
            "Country": oscar_address.country.code,
            "VerifyAddress": "false",
        }

    def format_postcode(self, raw_postcode: str | None) -> tuple[str, str]:
        # Split US-style ZIP+4 postcodes; send anything else (e.g. Canadian
        # postal codes) as-is.
        if match := ZIP_RE.match(raw_postcode or ""):
            return match.group(1), match.group(2) or ""
        return raw_postcode or "", ""
