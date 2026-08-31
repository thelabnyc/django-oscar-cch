from decimal import Decimal as D
from unittest import mock
import json

from django.core.exceptions import ImproperlyConfigured
from freezegun import freeze_time
from oscar.core.loading import get_class, get_model
from oscar.test import factories
import pybreaker
import requests
import requests_mock

from .. import exceptions
from ..models import OrderTaxation
from ..suretax import SureTaxCalculator
from ..types import TaxationResult
from .base import BaseTest

Basket = get_model("basket", "Basket")
USStrategy = get_class("partner.strategy", "US")


def suretax_url():
    from .. import settings

    return f"{settings.SURETAX_API_BASE_URL}/Services/V07/SureTax.asmx/PostRequest"


def suretax_tax_item(desc, amount, rate, authority, fee_rate=0):
    return {
        "TaxTypeCode": "010",
        "TaxTypeDesc": desc,
        "TaxAmount": str(amount),
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
                "TotalTax": str(total_tax),
                "TransId": trans_id,
                "STAN": "",
                "MasterTransId": trans_id,
                "GroupList": groups,
            }
        )
    }


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

        groups = [
            suretax_group(
                line_id,
                [
                    suretax_tax_item(
                        "STATE SALES TAX-GENERAL MERCHANDISE",
                        "0.90",
                        0.045,
                        "NEW YORK, STATE OF",
                    ),
                ],
            ),
        ]
        self.mock_suretax_response(rmock, json=suretax_response(groups, "0.90"))

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
        to_address = self.get_to_address()
        line_id = basket.all_lines()[0].id

        groups = [
            suretax_group(
                line_id,
                [
                    suretax_tax_item(
                        "STATE EXCISE TAX-MATTRESS",
                        "10.75",
                        0,
                        "CALIFORNIA, STATE OF",
                        fee_rate=10.75,
                    ),
                ],
            ),
        ]
        self.mock_suretax_response(rmock, json=suretax_response(groups, "10.75"))

        SureTaxCalculator().apply_taxes(to_address, basket)

        details = basket.all_lines()[0].purchase_info.price.taxation_details
        self.assertEqual(len(details), 1)
        self.assertEqual(details[0].tax_applied, D("0.00"))
        self.assertEqual(details[0].fee_applied, D("10.75"))
        self.assertEqual(basket.total_tax, D("10.75"))

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
    def test_apply_taxes_zero_qty_line_excluded(self, rmock):
        basket = self.prepare_basket(lines=2)
        to_address = self.get_to_address()
        basket.add_product(basket.all_lines()[0].product, -1)
        line_id = basket.all_lines()[1].id

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
                ],
            ),
        ]
        self.mock_suretax_response(rmock, json=suretax_response(groups, "0.40"))

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
    def test_apply_taxes_waf_403_retried(self, rmock):
        """A WAF 403 (rate-limit/size block) is an infrastructure error."""
        basket = self.prepare_basket()
        to_address = self.get_to_address()

        self.mock_suretax_response(rmock, status_code=403, text="Forbidden")

        resp = SureTaxCalculator().apply_taxes(to_address, basket)

        self.assertIsNone(resp)
        self.assertEqual(rmock.call_count, 3)
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
    def test_apply_taxes_http_error_retried(self, rmock):
        basket = self.prepare_basket()
        to_address = self.get_to_address()

        self.mock_suretax_response(rmock, status_code=500)

        resp = SureTaxCalculator().apply_taxes(to_address, basket)

        self.assertIsNone(resp)
        # Initial request plus SURETAX_MAX_RETRIES retries
        self.assertEqual(rmock.call_count, 3)
        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_tax, D("0.00"))

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @requests_mock.mock()
    def test_apply_taxes_read_timeout_retried(self, rmock):
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        line_id = basket.all_lines()[0].id

        # Throw a ReadTimeout, but only the first time.
        self.mock_suretax_response(
            rmock,
            [
                {"exc": requests.exceptions.ReadTimeout},
                {"json": self.get_normal_suretax_response(line_id)},
            ],
        )
        shipping_charge = self.get_shipping_charge()

        SureTaxCalculator().apply_taxes(to_address, basket, shipping_charge)

        self.assertEqual(rmock.call_count, 2)
        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_tax, D("0.89"))
        self.assertEqual(shipping_charge.incl_tax, D("16.3203625"))

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
    def test_apply_taxes_partial_payload(self, rmock):
        """A successful response missing a submitted line is treated as tax-unknown."""
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        shipping_charge = self.get_shipping_charge()
        line_id = basket.all_lines()[0].id

        # Response covers the basket line but not the shipping line
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
                ],
            ),
        ]
        self.mock_suretax_response(rmock, json=suretax_response(groups, "0.40"))

        resp = SureTaxCalculator().apply_taxes(to_address, basket, shipping_charge)

        self.assertIsNone(resp)
        self.assertEqual(rmock.call_count, 1)
        # No partial application: everything zeroed
        self.assertEqual(basket.total_tax, D("0.00"))
        self.assertEqual(shipping_charge.components[0].tax, D("0.00"))
        self.assertEqual(
            len(basket.all_lines()[0].purchase_info.price.taxation_details), 0
        )

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @requests_mock.mock()
    def test_apply_taxes_total_tax_mismatch(self, rmock):
        """A response whose TotalTax doesn't match the detail sum is tax-unknown."""
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        line_id = basket.all_lines()[0].id

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
                ],
            ),
        ]
        self.mock_suretax_response(rmock, json=suretax_response(groups, "9.99"))

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
    def test_apply_taxes_circuit_breaker_excludes_item_errors(self, rmock):
        """Business-level item errors don't trip an excluding circuit breaker."""
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

        circuit_breaker = pybreaker.CircuitBreaker(
            fail_max=2, reset_timeout=60, exclude=[exceptions.SureTaxItemError]
        )
        calc = SureTaxCalculator(breaker=circuit_breaker)
        calc.max_retries = 0

        # Breaker never opens, so every call reaches the web-service
        for expected_call_count in (1, 2, 3, 4):
            resp = calc.apply_taxes(to_address, basket)
            self.assertIsNone(resp)
            self.assertEqual(rmock.call_count, expected_call_count)


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
