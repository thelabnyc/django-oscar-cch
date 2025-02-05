from decimal import Decimal as D

from oscar.core.loading import get_class, get_model
from oscar.test import factories
import requests_mock

from .base import BaseTest

Basket = get_model("basket", "Basket")
ShippingAddress = get_model("order", "ShippingAddress")
Country = get_model("address", "Country")
USStrategy = get_class("partner.strategy", "US")


class PersistCCHDetailsTest(BaseTest):
    @requests_mock.mock()
    def test_persist_taxation_details(self, rmock):
        """Place an order with normal taxes"""
        basket = self.prepare_basket()
        to_address = self.get_to_address()

        self.mock_soap_response(
            rmock=rmock,
            text=self._get_cch_response_normal(basket.all_lines()[0].id),
        )

        # This should call CCH and save tax details in the DB
        order = factories.create_order(basket=basket, shipping_address=to_address)

        # Make sure we have an order taxation object
        self.assertEqual(order.taxation.transaction_id, 40043)
        self.assertEqual(order.taxation.transaction_status, 4)
        self.assertEqual(order.taxation.total_tax_applied, D("2.22"))
        self.assertEqual(order.taxation.messages, None)

        # Make sure we have a shipping taxation object
        self.assertEqual(order.shipping_taxations.count(), 1)
        shipping_taxation = order.shipping_taxations.first()
        self.assertEqual(shipping_taxation.country_code, "US")
        self.assertEqual(shipping_taxation.state_code, "NY")
        self.assertEqual(shipping_taxation.total_tax_applied, D("1.33"))
        self.assertEqual(shipping_taxation.details.count(), 3)
        for detail in shipping_taxation.details.all():
            self.assertIn("AuthorityName", detail.data)
            self.assertIn("TaxName", detail.data)
            self.assertIn("TaxRate", detail.data)
            self.assertTrue(float(detail.data["TaxRate"]) > 0)
            self.assertIn("TaxableAmount", detail.data)
            self.assertIn("TaxableQuantity", detail.data)

        # Make sure we have an line taxation objects
        for line in order.lines.all():
            self.assertEqual(line.taxation.country_code, "US")
            self.assertEqual(line.taxation.state_code, "NY")
            self.assertEqual(line.taxation.total_tax_applied, D("0.89"))
            self.assertEqual(line.taxation.details.count(), 3)
            for detail in line.taxation.details.all():
                self.assertIn("AuthorityName", detail.data)
                self.assertIn("TaxName", detail.data)
                self.assertIn("TaxRate", detail.data)
                self.assertTrue(float(detail.data["TaxRate"]) > 0)
                self.assertIn("TaxableAmount", detail.data)
                self.assertIn("TaxableQuantity", detail.data)

    @requests_mock.mock()
    def test_persist_taxation_details_when_zero(self, rmock):
        """Place a tax free order"""
        basket = self.prepare_basket()
        to_address = self.get_to_address()

        self.mock_soap_response(
            rmock=rmock,
            text=self._get_cch_response_empty(),
        )

        # This should call CCH and save tax details in the DB
        order = factories.create_order(basket=basket, shipping_address=to_address)

        # Make sure we have an order taxation object
        self.assertEqual(order.taxation.transaction_id, 40043)
        self.assertEqual(order.taxation.transaction_status, 4)
        self.assertEqual(order.taxation.total_tax_applied, D("0.00"))
        self.maxDiff = None
        self.assertJSONEqual(
            order.taxation.messages,
            [
                {
                    "Code": 0,
                    "Info": "OK",
                    "Reference": None,
                    "Severity": 0,
                    "Source": 0,
                    "TransactionStatus": 4,
                }
            ],
        )

        # Make sure we don't have a shipping taxation object
        self.assertEqual(order.shipping_taxations.count(), 0)

        # Make sure we have an line taxation objects
        for line in order.lines.all():
            self.assertFalse(hasattr(line, "taxation"))
