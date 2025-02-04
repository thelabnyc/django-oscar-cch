from decimal import Decimal as D

from django.test import TestCase
from oscar.apps.partner import prices
from oscar.core.loading import get_class, get_model
from oscar.core.prices import Price as CorePrice
from oscar.core.prices import TaxNotKnown

Basket = get_model("basket", "Basket")
BasketLine = get_model("basket", "Line")
ShippingAddress = get_model("order", "ShippingAddress")
Country = get_model("address", "Country")
USStrategy = get_class("partner.strategy", "US")


class FixedPriceTaxationDetailsTest(TestCase):
    def test_add_taxes(self):
        p = prices.FixedPrice("USD", D("10.00"))

        def get_incl_tax():
            return p.incl_tax

        self.assertEqual(p.excl_tax, D("10.00"))
        self.assertFalse(p.is_tax_known)
        self.assertRaises(TaxNotKnown, get_incl_tax)
        self.assertIsNone(p.tax)

        p.add_tax("New York State", "Sales Tax", tax_applied="1.00")

        self.assertEqual(p.excl_tax, D("10.00"))
        self.assertTrue(p.is_tax_known)
        self.assertEqual(p.incl_tax, D("11.00"))
        self.assertEqual(p.tax, D("1.00"))

        p.add_tax("IRS", "Some Fee", fee_applied="0.15")

        self.assertEqual(p.excl_tax, D("10.00"))
        self.assertTrue(p.is_tax_known)
        self.assertEqual(p.incl_tax, D("11.15"))
        self.assertEqual(p.tax, D("1.15"))

        self.assertEqual(p.taxation_details[0].authority_name, "New York State")
        self.assertEqual(p.taxation_details[0].tax_name, "Sales Tax")
        self.assertEqual(p.taxation_details[0].tax_applied, D("1.00"))
        self.assertEqual(p.taxation_details[0].fee_applied, D("0.00"))

        self.assertEqual(p.taxation_details[1].authority_name, "IRS")
        self.assertEqual(p.taxation_details[1].tax_name, "Some Fee")
        self.assertEqual(p.taxation_details[1].tax_applied, D("0.00"))
        self.assertEqual(p.taxation_details[1].fee_applied, D("0.15"))

        p.clear_taxes()

        self.assertEqual(p.excl_tax, D("10.00"))
        self.assertFalse(p.is_tax_known)
        self.assertRaises(TaxNotKnown, get_incl_tax)
        self.assertIsNone(p.tax)


class CorePriceTaxationDetailsTest(TestCase):
    def test_add_taxes(self):
        p = CorePrice("USD", D("10.00"))

        self.assertEqual(p.excl_tax, D("10.00"))
        self.assertFalse(p.is_tax_known)
        self.assertIsNone(p.incl_tax)

        p.add_tax("New York State", "Sales Tax", tax_applied="1.00")

        self.assertEqual(p.excl_tax, D("10.00"))
        self.assertTrue(p.is_tax_known)
        self.assertEqual(p.incl_tax, D("11.00"))
        self.assertEqual(p.tax, D("1.00"))

        p.add_tax("IRS", "Some Fee", fee_applied="0.15")

        self.assertEqual(p.excl_tax, D("10.00"))
        self.assertTrue(p.is_tax_known)
        self.assertEqual(p.incl_tax, D("11.15"))
        self.assertEqual(p.tax, D("1.15"))

        self.assertEqual(p.taxation_details[0].authority_name, "New York State")
        self.assertEqual(p.taxation_details[0].tax_name, "Sales Tax")
        self.assertEqual(p.taxation_details[0].tax_applied, D("1.00"))
        self.assertEqual(p.taxation_details[0].fee_applied, D("0.00"))

        self.assertEqual(p.taxation_details[1].authority_name, "IRS")
        self.assertEqual(p.taxation_details[1].tax_name, "Some Fee")
        self.assertEqual(p.taxation_details[1].tax_applied, D("0.00"))
        self.assertEqual(p.taxation_details[1].fee_applied, D("0.15"))

        p.clear_taxes()

        self.assertEqual(p.excl_tax, D("10.00"))
        self.assertFalse(p.is_tax_known)
        self.assertIsNone(p.incl_tax)
