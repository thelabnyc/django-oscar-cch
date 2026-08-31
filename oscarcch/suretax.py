from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
import json
import logging
import re

from django.core.exceptions import ImproperlyConfigured
from oscar.apps.basket.abstract_models import AbstractLine
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

ZIP_RE = re.compile(r"^(\d{5})(?:-(\d{4}))?$")

#: Header ResponseCode indicating full success
RESPONSE_CODE_SUCCESS = "9999"
#: Header ResponseCode indicating per-item validation errors
RESPONSE_CODE_ITEM_ERRORS = "9001"

#: TaxSitusRule: use all addresses to determine situs
SITUS_RULE_ALL_ADDRESSES = "22"
#: TaxSitusRule: use only the ship-to address to determine situs
SITUS_RULE_SHIP_TO = "23"


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
    timeout = settings.SURETAX_TIMEOUT
    max_retries = settings.SURETAX_MAX_RETRIES
    tax_name_map = settings.SURETAX_TAX_NAME_MAP

    def __init__(self, breaker: pybreaker.CircuitBreaker | None = None):
        """
        Construct a SureTaxCalculator instance

        You may optionally supply a ``pybreaker.CircuitBreaker`` instance. If you do so, it will be used to
        implement the CircuitBreaker pattern around the HTTP calls to the SureTax web service. Construct the
        breaker with ``exclude=[oscarcch.exceptions.SureTaxItemError]`` so that business-level item errors
        don't count as service failures.

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
        assert self.base_url is not None
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
        """Fetch SureTax tax data for the given basket and shipping address"""
        response = None
        retry_count = 0
        while response is None and retry_count <= self.max_retries:
            try:
                response = self._get_response_inner(
                    shipping_address, basket, shipping_charge
                )
            except exceptions.SureTaxError:
                # The service processed the request and reported an error;
                # retrying won't change the outcome.
                logger.exception("SureTax reported an error while calculating taxes")
                return None
            retry_count += 1
        return response

    def _get_response_inner(
        self,
        shipping_address: ShippingAddress | None,
        basket: Basket | None,
        shipping_charge: ShippingCharge | None,
    ) -> TaxationResult | None:
        def _call_service() -> TaxationResult | None:
            payload = self._build_request_payload(
                shipping_address, basket, shipping_charge
            )
            if payload is None:
                return None
            return self._post_and_parse(payload, shipping_address)

        try:
            if self.breaker is not None:
                return self.breaker.call(_call_service)
            return _call_service()
        except exceptions.SureTaxError:
            raise
        except Exception:
            logger.exception("Failed to fetch SureTax tax data")
            return None

    def _post_and_parse(
        self,
        payload: dict[str, Any],
        shipping_address: ShippingAddress | None,
    ) -> TaxationResult:
        # Credentials are deliberately never bound to a local variable: frame
        # locals get shipped to Sentry on capture_exception, and the default
        # scrubber doesn't recognize these field names.
        response = requests.post(
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
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        wrapper = response.json()
        envelope = wrapper.get("d") if isinstance(wrapper, dict) else None
        if not isinstance(envelope, str):
            raise requests.RequestException(
                "Unexpected SureTax response: missing 'd' envelope"
            )
        return self._parse_response(json.loads(envelope), payload, shipping_address)

    def _parse_response(
        self,
        data: dict[str, Any],
        payload: dict[str, Any],
        shipping_address: ShippingAddress | None,
    ) -> TaxationResult:
        response_code = str(data.get("ResponseCode", ""))
        if data.get("Successful") != "Y":
            raise exceptions.SureTaxError(
                response_code, str(data.get("HeaderMessage", ""))
            )
        if response_code == RESPONSE_CODE_ITEM_ERRORS:
            raise exceptions.SureTaxItemError(
                response_code, json.dumps(data.get("ItemMessages", []))
            )
        if response_code != RESPONSE_CODE_SUCCESS:
            raise exceptions.SureTaxError(
                response_code, str(data.get("HeaderMessage", ""))
            )

        # Group tax details by submitted line number
        submitted_line_ids = {item["LineNumber"] for item in payload["ItemList"]}
        grouped_details: dict[str, list[TaxDetailResult]] = {}
        state_codes: dict[str, str] = {}
        for group in data.get("GroupList") or []:
            line_id = str(group.get("LineNumber"))
            if line_id not in submitted_line_ids:
                raise exceptions.SureTaxError(
                    response_code,
                    f"Response contains unknown line number: {line_id}",
                )
            details = grouped_details.setdefault(line_id, [])
            state_codes.setdefault(line_id, str(group.get("StateCode") or ""))
            for tax in group.get("TaxList") or []:
                details.append(self._build_tax_detail(tax))

        # A "successful" response that doesn't cover every submitted line must
        # be treated as tax-unknown — never partially applied.
        missing_line_ids = submitted_line_ids - grouped_details.keys()
        if missing_line_ids:
            raise exceptions.SureTaxError(
                response_code,
                "Response does not cover submitted line numbers: "
                f"{sorted(missing_line_ids)}",
            )

        # Check our work and make sure the details sum to the total SureTax gave us
        total_tax = Decimal(str(data.get("TotalTax", "0")))
        details_total = sum(
            (
                detail.tax_applied + detail.fee_applied
                for details in grouped_details.values()
                for detail in details
            ),
            Decimal(0),
        )
        if details_total.quantize(self.precision) != total_tax.quantize(self.precision):
            raise exceptions.SureTaxError(
                response_code,
                "Taxation miscalculation occurred! "
                f"Details sum to {details_total}, which doesn't match "
                f"given sum of {total_tax}",
            )

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
        return TaxationResult(
            transaction_id=int(data["TransId"]),
            transaction_status=int(response_code),
            total_tax_applied=total_tax,
            messages=None,
            line_taxes=line_taxes,
        )

    def _build_tax_detail(self, tax: dict[str, Any]) -> TaxDetailResult:
        amount = Decimal(str(tax.get("TaxAmount", "0")))
        # Discriminate unit-based fees (e.g. recycling fees) from percentage
        # taxes: per the API docs, FeeRate is non-zero for fees.
        fee_rate = Decimal(str(tax.get("FeeRate") or 0))
        is_fee = fee_rate > 0
        revenue = Decimal(str(tax.get("Revenue") or 0))
        taxable_amount = Decimal(str(tax.get("RevenueBase") or revenue))
        tax_name = str(tax.get("TaxTypeDesc", ""))
        tax_name = self.tax_name_map.get(tax_name, tax_name)
        authority_name = str(tax.get("TaxAuthorityName", ""))
        tax_applied = Decimal(0) if is_fee else amount
        fee_applied = amount if is_fee else Decimal(0)
        taxable_quantity = amount / fee_rate if is_fee else Decimal(0)
        # Persist the native SureTax fields, plus the CCH key vocabulary that
        # downstream consumers of the HStore data match on.
        data = {str(k): str(v) for k, v in tax.items()}
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
        trans_date = f"{now:%m/%d/%Y}"
        items: list[dict[str, Any]] = []

        # Add items for each basket line
        if basket is not None:
            for line in basket.all_lines():
                qty = getattr(line, "cch_quantity", line.quantity)
                if qty <= 0:
                    continue
                line_price = line.line_price_excl_tax_incl_discounts
                assert line_price is not None
                item: dict[str, Any] = {
                    "LineNumber": str(line.id),
                    "TransDate": trans_date,
                    "Revenue": str(Decimal(line_price).quantize(self.precision)),
                    "Units": str(qty),
                    "TaxIncludedCode": "0",
                    "TaxSitusRule": SITUS_RULE_SHIP_TO,
                    "TransTypeCode": self._get_product_data("sku", line),
                    "SalesTypeCode": "T",
                    "RegulatoryCode": "70",
                }
                if shipping_address is not None:
                    item["ShipToAddress"] = self._build_address(shipping_address)
                warehouse = line.stockrecord.partner.primary_address
                if warehouse:
                    item["ShipFromAddress"] = self._build_address(warehouse)
                    item["TaxSitusRule"] = SITUS_RULE_ALL_ADDRESSES
                items.append(item)

        # Add items for shipping charges
        if shipping_charge is not None and settings.CCH_SHIPPING_TAXES_ENABLED:
            for shipping_charge_component in shipping_charge.components:
                shipping_item: dict[str, Any] = {
                    "LineNumber": shipping_charge_component.cch_line_id,
                    "TransDate": trans_date,
                    "Revenue": str(
                        shipping_charge_component.excl_tax.quantize(self.precision)
                    ),
                    "Units": "1",
                    "TaxIncludedCode": "0",
                    "TaxSitusRule": SITUS_RULE_SHIP_TO,
                    "TransTypeCode": shipping_charge_component.cch_sku,
                    "SalesTypeCode": "T",
                    "RegulatoryCode": "70",
                }
                if shipping_address is not None:
                    shipping_item["ShipToAddress"] = self._build_address(
                        shipping_address
                    )
                items.append(shipping_item)

        # Must include at least 1 item
        if len(items) <= 0:
            return None

        total_revenue = sum(
            (Decimal(item["Revenue"]) for item in items),
            Decimal(0),
        )
        return {
            "DataYear": f"{now:%Y}",
            "DataMonth": f"{now:%m}",
            "CmplDataYear": f"{now:%Y}",
            "CmplDataMonth": f"{now:%m}",
            "TotalRevenue": str(total_revenue),
            "ReturnFileCode": "Q",
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

    def _get_product_data(
        self,
        key: str,
        line: AbstractLine,
    ) -> str:
        key = f"cch_product_{key}"
        sku = getattr(settings, key.upper())
        sku = getattr(line.product.attr, key.lower(), sku)
        return sku

    def format_postcode(self, raw_postcode: str) -> tuple[str, str]:
        if not raw_postcode:
            return "", ""
        # Split US-style ZIP+4 postcodes; send anything else (e.g. Canadian
        # postal codes) as-is.
        match = ZIP_RE.match(raw_postcode)
        if match:
            return match.group(1), match.group(2) or ""
        return raw_postcode, ""
