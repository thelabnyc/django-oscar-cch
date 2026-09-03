from decimal import Decimal as D
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar
from unittest import mock
import json
import threading
import time

from django.core.exceptions import ImproperlyConfigured
from freezegun import freeze_time
from oscar.core.loading import get_class, get_model
from oscar.test import factories
import pybreaker
import requests
import requests_mock

from ..models import OrderTaxation
from ..suretax import SureTaxCalculator
from ..types import TaxationResult
from .base import BaseTest

Basket = get_model("basket", "Basket")
USStrategy = get_class("partner.strategy", "US")


def suretax_url():
    from .. import settings

    return f"{settings.SURETAX_API_BASE_URL}/Services/V07/SureTax.asmx/PostRequest"


def _num(value):
    # The API sends JSON null rather than omitting an empty numeric field.
    return None if value is None else str(value)


def suretax_tax_item(desc, amount, rate, authority, fee_rate=0):
    return {
        "TaxTypeCode": "010",
        "TaxTypeDesc": desc,
        "TaxAmount": _num(amount),
        "Revenue": "10.00",
        "CountyName": "KINGS",
        "CityName": "BROOKLYN",
        "TaxRate": rate,
        "PercentTaxable": 1.0,
        "FeeRate": fee_rate,
        "RevenueBase": "10.00",
        "TaxOnTax": "0",
        "TaxAuthorityID": "12345",
        "TaxAuthorityName": authority,
        "Juriscode": "",
    }


def suretax_group(line_number, taxes):
    return {
        "LineNumber": str(line_number),
        "StateCode": "NY",
        "InvoiceNumber": "",
        "CustomerNumber": "",
        "LocationCode": "",
        "TaxList": taxes,
    }


def suretax_response(
    groups,
    total_tax,
    trans_id=8888840043,
    successful="Y",
    response_code="9999",
    header_message="Success",
    item_messages=None,
):
    return {
        "d": json.dumps(
            {
                "Successful": successful,
                "ResponseCode": response_code,
                "HeaderMessage": header_message,
                "ItemMessages": item_messages or [],
                "ClientTracking": "",
                "TotalTax": _num(total_tax),
                "TransId": trans_id,
                "STAN": "",
                "MasterTransId": trans_id,
                "GroupList": groups,
            }
        )
    }


def single_tax_response(line_id, amount, total_tax=None):
    """Response with one line carrying a single NY state sales tax of ``amount``."""
    tax = suretax_tax_item(
        "STATE SALES TAX-GENERAL MERCHANDISE", amount, 0.04, "NEW YORK, STATE OF"
    )
    groups = [suretax_group(line_id, [tax])]
    return suretax_response(groups, amount if total_tax is None else total_tax)


class SureTaxTestMixin:
    def mock_suretax_response(self, rmock, *args, **kwargs):
        rmock.register_uri("POST", suretax_url(), *args, **kwargs)

    def get_normal_suretax_response(self, line_id):
        groups = [
            suretax_group(
                line_id,
                [
                    suretax_tax_item(
                        "STATE SALES TAX-GENERAL MERCHANDISE",
                        "0.40",
                        0.04,
                        "NEW YORK, STATE OF",
                    ),
                    suretax_tax_item(
                        "COUNTY SALES TAX-GENERAL MERCHANDISE",
                        "0.45",
                        0.045,
                        "NEW YORK, CITY OF",
                    ),
                    suretax_tax_item(
                        "COUNTY LOCAL SALES TAX-GENERAL MERCHANDISE",
                        "0.04",
                        0.00375,
                        "METROPOLITAN TRANSPORTATION AUTHORITY",
                    ),
                ],
            ),
            suretax_group(
                "shipping:PARCEL:0",
                [
                    suretax_tax_item(
                        "STATE SALES TAX-GENERAL MERCHANDISE",
                        "0.5996",
                        0.04,
                        "NEW YORK, STATE OF",
                    ),
                    suretax_tax_item(
                        "COUNTY SALES TAX-GENERAL MERCHANDISE",
                        "0.67455",
                        0.045,
                        "NEW YORK, CITY OF",
                    ),
                    suretax_tax_item(
                        "COUNTY LOCAL SALES TAX-GENERAL MERCHANDISE",
                        "0.0562125",
                        0.00375,
                        "METROPOLITAN TRANSPORTATION AUTHORITY",
                    ),
                ],
            ),
        ]
        return suretax_response(groups, "2.2203625")

    def get_suretax_request(self, rmock, index=-1):
        return json.loads(rmock.request_history[index].json()["request"])


class SureTaxCalculatorTest(SureTaxTestMixin, BaseTest):
    def test_unconfigured_fails_loud(self):
        with (
            mock.patch.object(SureTaxCalculator, "validation_key", ""),
            self.assertRaises(ImproperlyConfigured),
        ):
            SureTaxCalculator()

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @requests_mock.mock()
    def test_apply_taxes_normal(self, rmock):
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        shipping_charge = self.get_shipping_charge()
        line_id = basket.all_lines()[0].id

        self.mock_suretax_response(
            rmock, json=self.get_normal_suretax_response(line_id)
        )

        self.assertFalse(basket.is_tax_known)
        resp = SureTaxCalculator().apply_taxes(to_address, basket, shipping_charge)

        # Check the request that was sent
        self.assertEqual(rmock.call_count, 1)
        self.assertEqual(rmock.request_history[0].timeout, (3.05, 10))
        request_data = self.get_suretax_request(rmock)
        self.assertEqual(
            request_data,
            {
                "ClientNumber": "000000123",
                "ValidationKey": "00000000-0000-0000-0000-000000000000",
                "BusinessUnit": "TESTSANDBOX",
                "DataYear": "2016",
                "DataMonth": "04",
                "CmplDataYear": "2016",
                "CmplDataMonth": "04",
                "TotalRevenue": "24.99",
                "ReturnFileCode": "Q",
                "ResponseType": "D2",
                "ResponseGroup": "00",
                "STAN": "",
                "ItemList": [
                    {
                        "LineNumber": str(line_id),
                        "TransDate": "04/13/2016",
                        "Revenue": "10.00",
                        "Units": "1",
                        "TaxIncludedCode": "0",
                        "TaxSitusRule": "22",
                        "TransTypeCode": "ABC123",
                        "SalesTypeCode": "T",
                        "RegulatoryCode": "70",
                        "ShipToAddress": {
                            "PrimaryAddressLine": "123 Evergreen Terrace",
                            "SecondaryAddressLine": "Apt #1",
                            "City": "Brooklyn",
                            "State": "NY",
                            "PostalCode": "11201",
                            "Plus4": "",
                            "Country": "US",
                            "VerifyAddress": "false",
                        },
                        "ShipFromAddress": {
                            "PrimaryAddressLine": "221 Baker st",
                            "SecondaryAddressLine": "B",
                            "City": "Anchorage",
                            "State": "AK",
                            "PostalCode": "99501",
                            "Plus4": "",
                            "Country": "US",
                            "VerifyAddress": "false",
                        },
                    },
                    {
                        "LineNumber": "shipping:PARCEL:0",
                        "TransDate": "04/13/2016",
                        "Revenue": "14.99",
                        "Units": "1",
                        "TaxIncludedCode": "0",
                        "TaxSitusRule": "23",
                        "TransTypeCode": "PARCEL",
                        "SalesTypeCode": "T",
                        "RegulatoryCode": "70",
                        "ShipToAddress": {
                            "PrimaryAddressLine": "123 Evergreen Terrace",
                            "SecondaryAddressLine": "Apt #1",
                            "City": "Brooklyn",
                            "State": "NY",
                            "PostalCode": "11201",
                            "Plus4": "",
                            "Country": "US",
                            "VerifyAddress": "false",
                        },
                    },
                ],
            },
        )

        # Check the response was applied
        self.assertIsInstance(resp, TaxationResult)
        self.assertEqual(resp.transaction_id, 8888840043)
        self.assertEqual(resp.transaction_status, 9999)
        self.assertEqual(resp.total_tax_applied, D("2.2203625"))
        self.assertIsNone(resp.messages)

        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D("10.00"))
        self.assertEqual(basket.total_incl_tax, D("10.89"))
        self.assertEqual(basket.total_tax, D("0.89"))

        purchase_info = basket.all_lines()[0].purchase_info
        details = purchase_info.price.taxation_details
        self.assertEqual(len(details), 3)
        self.assertEqual(details[0].authority_name, "NEW YORK, STATE OF")
        self.assertEqual(details[0].tax_name, "STATE SALES TAX-GENERAL MERCHANDISE")
        self.assertEqual(details[0].tax_applied, D("0.40"))
        self.assertEqual(details[0].fee_applied, D("0.00"))

        self.assertTrue(shipping_charge.is_tax_known)
        self.assertEqual(shipping_charge.excl_tax, D("14.99"))
        self.assertEqual(shipping_charge.incl_tax, D("16.3203625"))
        self.assertEqual(len(shipping_charge.components[0].taxation_details), 3)
        self.assertEqual(
            shipping_charge.components[0].taxation_details[0].tax_applied,
            D("0.5996"),
        )

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @requests_mock.mock()
    def test_apply_taxes_quantity_division(self, rmock):
        basket = self.prepare_basket()
        basket.add_product(basket.all_lines()[0].product, 1)
        to_address = self.get_to_address()
        line_id = basket.all_lines()[0].id

        self.mock_suretax_response(rmock, json=single_tax_response(line_id, "0.90"))

        SureTaxCalculator().apply_taxes(to_address, basket)

        request_data = self.get_suretax_request(rmock)
        self.assertEqual(request_data["TotalRevenue"], "20.00")
        self.assertEqual(request_data["ItemList"][0]["Revenue"], "20.00")
        self.assertEqual(request_data["ItemList"][0]["Units"], "2")

        # Line-level tax is divided by quantity to get unit tax
        purchase_info = basket.all_lines()[0].purchase_info
        self.assertEqual(purchase_info.price.tax, D("0.45"))
        self.assertEqual(basket.total_tax, D("0.90"))

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @requests_mock.mock()
    def test_apply_taxes_unit_fee(self, rmock):
        """Unit-based fees (FeeRate > 0) populate fee_applied, not tax_applied."""
        basket = self.prepare_basket()
        basket.add_product(basket.all_lines()[0].product, 1)
        to_address = self.get_to_address()
        line_id = basket.all_lines()[0].id

        # SureTax scales FeeRate by the submitted Units: 10.75/unit x 2 units.
        groups = [
            suretax_group(
                line_id,
                [
                    suretax_tax_item(
                        "STATE EXCISE TAX-MATTRESS",
                        "21.50",
                        0,
                        "CALIFORNIA, STATE OF",
                        fee_rate=21.5,
                    ),
                ],
            ),
        ]
        self.mock_suretax_response(rmock, json=suretax_response(groups, "21.50"))

        resp = SureTaxCalculator().apply_taxes(to_address, basket)

        details = basket.all_lines()[0].purchase_info.price.taxation_details
        self.assertEqual(len(details), 1)
        self.assertEqual(details[0].tax_applied, D("0.00"))
        self.assertEqual(details[0].fee_applied, D("10.75"))
        self.assertEqual(basket.total_tax, D("21.50"))

        # Persisted quantity is the line quantity, as with CCH STO
        detail_data = resp.line_taxes[0].details[0].data
        self.assertEqual(detail_data["FeeApplied"], "21.50")
        self.assertEqual(detail_data["TaxableQuantity"], "2")

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @requests_mock.mock()
    def test_apply_taxes_tax_name_map(self, rmock):
        """SureTax tax descriptions are mapped back to legacy CCH tax names."""
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        line_id = basket.all_lines()[0].id

        groups = [
            suretax_group(
                line_id,
                [
                    suretax_tax_item(
                        "RETAIL DELIVERY FEE",
                        "0.29",
                        0,
                        "COLORADO, STATE OF",
                        fee_rate=0.29,
                    ),
                ],
            ),
        ]
        self.mock_suretax_response(rmock, json=suretax_response(groups, "0.29"))

        name_map = {"RETAIL DELIVERY FEE": "MISC. SURCHARGE 2-FLAT FEE"}
        with mock.patch.object(SureTaxCalculator, "tax_name_map", name_map):
            SureTaxCalculator().apply_taxes(to_address, basket)

        details = basket.all_lines()[0].purchase_info.price.taxation_details
        self.assertEqual(details[0].tax_name, "MISC. SURCHARGE 2-FLAT FEE")

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @requests_mock.mock()
    def test_apply_taxes_tax_free(self, rmock):
        """A line covered by the response but with no taxes gets zero tax."""
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        line_id = basket.all_lines()[0].id

        groups = [suretax_group(line_id, [])]
        self.mock_suretax_response(rmock, json=suretax_response(groups, "0"))

        resp = SureTaxCalculator().apply_taxes(to_address, basket)

        self.assertIsInstance(resp, TaxationResult)
        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_tax, D("0.00"))
        details = basket.all_lines()[0].purchase_info.price.taxation_details
        self.assertEqual(len(details), 0)

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @requests_mock.mock()
    def test_apply_taxes_null_amounts(self, rmock):
        """Null numeric fields are read as zero, not as a parse failure."""
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        line_id = basket.all_lines()[0].id

        self.mock_suretax_response(rmock, json=single_tax_response(line_id, None))

        resp = SureTaxCalculator().apply_taxes(to_address, basket)

        self.assertIsInstance(resp, TaxationResult)
        self.assertEqual(rmock.call_count, 1)
        self.assertEqual(resp.total_tax_applied, D("0.00"))
        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_tax, D("0.00"))

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @requests_mock.mock()
    def test_apply_taxes_percent_taxable(self, rmock):
        """TaxableAmount derives from Revenue * PercentTaxable, not RevenueBase."""
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        line_id = basket.all_lines()[0].id

        partial = suretax_tax_item(
            "STATE SALES TAX-GENERAL MERCHANDISE", "0.20", 0.04, "NEW YORK, STATE OF"
        )
        partial["PercentTaxable"] = 0.5
        # RevenueBase is back-computed from the rounded tax and can exceed Revenue
        partial["RevenueBase"] = "10.01"
        missing = suretax_tax_item(
            "COUNTY SALES TAX-GENERAL MERCHANDISE", "0.45", 0.045, "NEW YORK, CITY OF"
        )
        del missing["PercentTaxable"]
        groups = [suretax_group(line_id, [partial, missing])]
        self.mock_suretax_response(rmock, json=suretax_response(groups, "0.65"))

        resp = SureTaxCalculator().apply_taxes(to_address, basket)

        partial_data, missing_data = (d.data for d in resp.line_taxes[0].details)
        self.assertEqual(partial_data["TaxableAmount"], "5.00")
        self.assertEqual(partial_data["ExemptAmt"], "5.00")
        # Absent PercentTaxable means fully taxable
        self.assertEqual(missing_data["TaxableAmount"], "10.00")
        self.assertEqual(missing_data["ExemptAmt"], "0.00")

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @requests_mock.mock()
    def test_apply_taxes_zero_qty_line_excluded(self, rmock):
        basket = self.prepare_basket(lines=2)
        to_address = self.get_to_address()
        basket.add_product(basket.all_lines()[0].product, -1)
        line_id = basket.all_lines()[1].id

        self.mock_suretax_response(rmock, json=single_tax_response(line_id, "0.40"))

        resp = SureTaxCalculator().apply_taxes(to_address, basket)

        request_data = self.get_suretax_request(rmock)
        self.assertEqual(len(request_data["ItemList"]), 1)
        self.assertEqual(request_data["ItemList"][0]["LineNumber"], str(line_id))
        self.assertIsInstance(resp, TaxationResult)
        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_tax, D("0.40"))

    def test_apply_taxes_empty_basket(self):
        basket = Basket()
        basket.strategy = USStrategy()
        to_address = self.get_to_address()

        with requests_mock.mock() as rmock:
            self.mock_suretax_response(rmock, json={"d": "{}"})
            resp = SureTaxCalculator().apply_taxes(to_address, basket)

        self.assertIsNone(resp)
        self.assertEqual(rmock.call_count, 0)

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @requests_mock.mock()
    def test_apply_taxes_header_error_not_retried(self, rmock):
        """A header-level API error (e.g. bad credentials) fails without retry."""
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        shipping_charge = self.get_shipping_charge()

        self.mock_suretax_response(
            rmock,
            json=suretax_response(
                [],
                "0",
                successful="N",
                response_code="1101",
                header_message="Invalid ClientNumber",
            ),
        )

        resp = SureTaxCalculator().apply_taxes(to_address, basket, shipping_charge)

        self.assertIsNone(resp)
        self.assertEqual(rmock.call_count, 1)
        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_tax, D("0.00"))
        self.assertEqual(shipping_charge.components[0].tax, D("0.00"))

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @requests_mock.mock()
    def test_apply_taxes_revenue_mismatch_error_not_retried(self, rmock):
        """A 1191 (TotalRevenue doesn't match item sum) error fails without retry."""
        basket = self.prepare_basket()
        to_address = self.get_to_address()

        self.mock_suretax_response(
            rmock,
            json=suretax_response(
                [],
                "0",
                successful="N",
                response_code="1191",
                header_message="TotalRevenue does not match sum of item revenues",
            ),
        )

        resp = SureTaxCalculator().apply_taxes(to_address, basket)

        self.assertIsNone(resp)
        self.assertEqual(rmock.call_count, 1)
        self.assertEqual(basket.total_tax, D("0.00"))

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @requests_mock.mock()
    def test_apply_taxes_item_errors_not_retried(self, rmock):
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        line_id = basket.all_lines()[0].id

        self.mock_suretax_response(
            rmock,
            json=suretax_response(
                [],
                "0",
                response_code="9001",
                header_message="Success with Item errors",
                item_messages=[
                    {
                        "LineNumber": str(line_id),
                        "ResponseCode": "9330",
                        "Message": "Invalid TransTypeCode",
                    }
                ],
            ),
        )

        resp = SureTaxCalculator().apply_taxes(to_address, basket)

        self.assertIsNone(resp)
        self.assertEqual(rmock.call_count, 1)
        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_tax, D("0.00"))

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @requests_mock.mock()
    def test_apply_taxes_transport_error(self, rmock):
        """An exhausted transport failure returns None (so the order is placed
        tax-unknown) while basket prices are zeroed and marked tax-known,
        mirroring the CCH backend."""
        basket = self.prepare_basket()
        to_address = self.get_to_address()

        self.mock_suretax_response(rmock, exc=requests.exceptions.ReadTimeout)

        resp = SureTaxCalculator().apply_taxes(to_address, basket)

        self.assertIsNone(resp)
        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_tax, D("0.00"))

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @requests_mock.mock()
    def test_apply_taxes_malformed_envelope(self, rmock):
        basket = self.prepare_basket()
        to_address = self.get_to_address()

        self.mock_suretax_response(rmock, json={"d": 12345})

        resp = SureTaxCalculator().apply_taxes(to_address, basket)

        self.assertIsNone(resp)
        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_tax, D("0.00"))

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @requests_mock.mock()
    def test_apply_taxes_malformed_success_body(self, rmock):
        """A success envelope missing TransId degrades to tax-unknown, not a crash."""
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        line_id = basket.all_lines()[0].id

        body = json.loads(single_tax_response(line_id, "0.40")["d"])
        del body["TransId"]
        self.mock_suretax_response(rmock, json={"d": json.dumps(body)})

        resp = SureTaxCalculator().apply_taxes(to_address, basket)

        self.assertIsNone(resp)
        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_tax, D("0.00"))

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @requests_mock.mock()
    def test_apply_taxes_postcode_formats(self, rmock):
        """ZIP+4 is split into PostalCode/Plus4; other postcodes pass through."""
        basket = self.prepare_basket()
        line_id = basket.all_lines()[0].id
        self.mock_suretax_response(rmock, json=single_tax_response(line_id, "0.40"))

        to_address = self.get_to_address_ohio_full_zip()
        SureTaxCalculator().apply_taxes(to_address, basket)
        ship_to = self.get_suretax_request(rmock)["ItemList"][0]["ShipToAddress"]
        self.assertEqual(ship_to["PostalCode"], "43006")
        self.assertEqual(ship_to["Plus4"], "9000")

        to_address.postcode = "K1A 0B1"
        SureTaxCalculator().apply_taxes(to_address, basket)
        ship_to = self.get_suretax_request(rmock)["ItemList"][0]["ShipToAddress"]
        self.assertEqual(ship_to["PostalCode"], "K1A 0B1")
        self.assertEqual(ship_to["Plus4"], "")

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @requests_mock.mock()
    def test_apply_taxes_custom_quantity(self, rmock):
        """A line's cch_quantity override drives the Units sent to SureTax."""
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        line_id = basket.all_lines()[0].id
        for line in basket.all_lines():
            line.cch_quantity = 3
        self.mock_suretax_response(rmock, json=single_tax_response(line_id, "0.40"))

        SureTaxCalculator().apply_taxes(to_address, basket)

        item = self.get_suretax_request(rmock)["ItemList"][0]
        self.assertEqual(item["Units"], "3")
        self.assertEqual(item["Revenue"], "10.00")

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @requests_mock.mock()
    def test_apply_taxes_omitted_line_is_tax_free(self, rmock):
        """SureTax omits zero-tax lines from GroupList; they get zero tax, not tax-unknown."""
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        shipping_charge = self.get_shipping_charge()
        line_id = basket.all_lines()[0].id

        # Response covers the basket line but not the (untaxed) shipping line
        self.mock_suretax_response(rmock, json=single_tax_response(line_id, "0.40"))

        resp = SureTaxCalculator().apply_taxes(to_address, basket, shipping_charge)

        self.assertIsInstance(resp, TaxationResult)
        self.assertEqual(rmock.call_count, 1)
        self.assertEqual([lt.line_id for lt in resp.line_taxes], [str(line_id)])
        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_tax, D("0.40"))
        self.assertTrue(shipping_charge.is_tax_known)
        self.assertEqual(shipping_charge.components[0].tax, D("0.00"))
        self.assertEqual(len(shipping_charge.components[0].taxation_details), 0)

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @requests_mock.mock()
    def test_apply_taxes_total_tax_mismatch(self, rmock):
        """A response whose TotalTax doesn't match the detail sum is tax-unknown."""
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        line_id = basket.all_lines()[0].id

        self.mock_suretax_response(
            rmock, json=single_tax_response(line_id, "0.40", total_tax="9.99")
        )

        resp = SureTaxCalculator().apply_taxes(to_address, basket)

        self.assertIsNone(resp)
        self.assertEqual(rmock.call_count, 1)
        self.assertEqual(basket.total_tax, D("0.00"))

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @requests_mock.mock()
    def test_apply_taxes_circuit_breaker(self, rmock):
        basket = self.prepare_basket()
        to_address = self.get_to_address()

        self.mock_suretax_response(rmock, exc=requests.exceptions.ReadTimeout)

        circuit_breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=60)
        calc = SureTaxCalculator(breaker=circuit_breaker)
        calc.max_retries = 0

        for expected_call_count in (1, 2, 3):
            resp = calc.apply_taxes(to_address, basket)
            self.assertIsNone(resp)
            self.assertEqual(rmock.call_count, expected_call_count)

        # Circuit is now open; web-service isn't called anymore
        resp = calc.apply_taxes(to_address, basket)
        self.assertIsNone(resp)
        self.assertEqual(rmock.call_count, 3)

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @requests_mock.mock()
    def test_apply_taxes_circuit_breaker_ignores_item_errors(self, rmock):
        """Errors reported in the response body don't trip a plain circuit breaker."""
        basket = self.prepare_basket()
        to_address = self.get_to_address()

        self.mock_suretax_response(
            rmock,
            json=suretax_response(
                [],
                "0",
                response_code="9001",
                header_message="Success with Item errors",
                item_messages=[
                    {"LineNumber": "1", "ResponseCode": "9330", "Message": "Bad"}
                ],
            ),
        )

        circuit_breaker = pybreaker.CircuitBreaker(fail_max=2, reset_timeout=60)
        calc = SureTaxCalculator(breaker=circuit_breaker)
        calc.max_retries = 0

        # Breaker never opens, so every call reaches the web-service
        for expected_call_count in (1, 2, 3, 4):
            resp = calc.apply_taxes(to_address, basket)
            self.assertIsNone(resp)
            self.assertEqual(rmock.call_count, expected_call_count)


class ScriptedSureTaxHandler(BaseHTTPRequestHandler):
    """Serves a scripted list of (status, body) responses, repeating the last."""

    script: ClassVar[list] = []
    requests_seen: ClassVar[list] = []
    #: Seconds to stall the first request, to provoke a client read timeout.
    first_request_delay: ClassVar[float] = 0

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        self.requests_seen.append(json.loads(body))
        if len(self.requests_seen) == 1 and self.first_request_delay:
            time.sleep(self.first_request_delay)
        status, payload = self.script[
            min(len(self.requests_seen), len(self.script)) - 1
        ]
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())
        except BrokenPipeError:
            pass  # client gave up (read timeout) before we answered

    def log_message(self, *args):
        pass


class SureTaxRetryTest(SureTaxTestMixin, BaseTest):
    """
    Retries live in urllib3's transport adapter, which requests_mock bypasses,
    so exercise them against a real local HTTP server.
    """

    def setUp(self):
        super().setUp()
        ScriptedSureTaxHandler.requests_seen = []
        ScriptedSureTaxHandler.first_request_delay = 0
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ScriptedSureTaxHandler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        patcher = mock.patch.object(
            SureTaxCalculator, "base_url", f"http://127.0.0.1:{self.server.server_port}"
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    def test_transient_status_retried_then_succeeds(self):
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        line_id = basket.all_lines()[0].id
        ScriptedSureTaxHandler.script = [
            (500, {}),
            (200, self.get_normal_suretax_response(line_id)),
        ]

        shipping_charge = self.get_shipping_charge()

        resp = SureTaxCalculator().apply_taxes(to_address, basket, shipping_charge)

        self.assertIsInstance(resp, TaxationResult)
        self.assertEqual(len(ScriptedSureTaxHandler.requests_seen), 2)
        self.assertEqual(basket.total_tax, D("0.89"))
        self.assertEqual(shipping_charge.incl_tax, D("16.3203625"))

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    def test_waf_403_retried_until_exhausted(self):
        """A WAF 403 (rate-limit/size block) is an infrastructure error."""
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        ScriptedSureTaxHandler.script = [(403, {})]

        resp = SureTaxCalculator().apply_taxes(to_address, basket)

        self.assertIsNone(resp)
        # Initial request plus SURETAX_MAX_RETRIES retries
        self.assertEqual(len(ScriptedSureTaxHandler.requests_seen), 3)
        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_tax, D("0.00"))

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    def test_read_timeout_retried_then_succeeds(self):
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        line_id = basket.all_lines()[0].id
        ScriptedSureTaxHandler.first_request_delay = 1
        ScriptedSureTaxHandler.script = [(200, single_tax_response(line_id, "0.40"))]

        calc = SureTaxCalculator()
        calc.timeout = (1, 0.25)
        resp = calc.apply_taxes(to_address, basket)

        self.assertIsInstance(resp, TaxationResult)
        self.assertEqual(len(ScriptedSureTaxHandler.requests_seen), 2)
        self.assertEqual(basket.total_tax, D("0.40"))


class PersistSureTaxDetailsTest(SureTaxTestMixin, BaseTest):
    @requests_mock.mock()
    def test_persist_taxation_details(self, rmock):
        basket = self.prepare_basket()
        to_address = self.get_to_address()

        # Place the order without tax data (simulated CCH outage), then
        # calculate and persist taxes using SureTax.
        self.mock_soap_response(
            rmock=rmock,
            text=self._get_cch_response_db_connection_error(),
        )
        order = factories.create_order(basket=basket, shipping_address=to_address)
        self.assertFalse(hasattr(order, "taxation"))

        line_id = order.lines.first().basket_line_id
        self.mock_suretax_response(
            rmock, json=self.get_normal_suretax_response(line_id)
        )
        shipping_charge = self.get_shipping_charge()
        resp = SureTaxCalculator().apply_taxes(to_address, basket, shipping_charge)
        OrderTaxation.save_details(order, resp)

        order.refresh_from_db()
        # Transaction ID larger than 32 bits must persist
        self.assertEqual(order.taxation.transaction_id, 8888840043)
        self.assertEqual(order.taxation.transaction_status, 9999)
        self.assertEqual(order.taxation.total_tax_applied, D("2.22"))
        self.assertIsNone(order.taxation.messages)

        line = order.lines.first()
        self.assertEqual(line.taxation.country_code, "US")
        self.assertEqual(line.taxation.state_code, "NY")
        self.assertEqual(line.taxation.total_tax_applied, D("0.89"))
        self.assertEqual(line.taxation.details.count(), 3)
        detail_data = line.taxation.details.first().data
        # Normalized CCH-vocabulary keys
        self.assertEqual(detail_data["TaxName"], "STATE SALES TAX-GENERAL MERCHANDISE")
        self.assertEqual(detail_data["AuthorityName"], "NEW YORK, STATE OF")
        self.assertEqual(detail_data["TaxApplied"], "0.40")
        self.assertEqual(detail_data["FeeApplied"], "0")
        self.assertEqual(detail_data["TaxableAmount"], "10.00")
        self.assertEqual(detail_data["ExemptAmt"], "0.00")
        self.assertEqual(detail_data["TaxableQuantity"], "0")
        self.assertEqual(detail_data["ExemptQty"], "0")
        # Native SureTax keys ride along
        self.assertEqual(
            detail_data["TaxTypeDesc"], "STATE SALES TAX-GENERAL MERCHANDISE"
        )
        self.assertEqual(detail_data["TaxRate"], "0.04")
        self.assertEqual(detail_data["TaxAuthorityName"], "NEW YORK, STATE OF")

        self.assertEqual(order.shipping_taxations.count(), 1)
        shipping_taxation = order.shipping_taxations.first()
        self.assertEqual(shipping_taxation.cch_line_id, "shipping:PARCEL:0")
        self.assertEqual(shipping_taxation.country_code, "US")
        self.assertEqual(shipping_taxation.state_code, "NY")
        self.assertEqual(shipping_taxation.total_tax_applied, D("1.33"))
        self.assertEqual(shipping_taxation.details.count(), 3)
