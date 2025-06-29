from decimal import Decimal as D
import unittest

from oscar.core.loading import get_class, get_model

from ..calculator import CCHTaxCalculator
from .base import BaseTest

Basket = get_model("basket", "Basket")
ShippingAddress = get_model("order", "ShippingAddress")
Country = get_model("address", "Country")
PartnerAddress = get_model("partner", "PartnerAddress")
Range = get_model("offer", "Range")
Benefit = get_model("offer", "Benefit")
Condition = get_model("offer", "Condition")
ConditionalOffer = get_model("offer", "ConditionalOffer")

USStrategy = get_class("partner.strategy", "US")
Applicator = get_class("offer.applicator", "Applicator")


@unittest.skip("Disabled because it uses real cch")
class CCHTaxCalculatorRealTest(BaseTest):
    def test_apply_taxes_five_digits_postal_code(self):
        basket = self.prepare_basket_full_zip()
        to_address = self.get_to_address_ohio_short_zip()
        shipping_charge = self.get_shipping_charge()

        CCHTaxCalculator().apply_taxes(to_address, basket, shipping_charge)

        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D("10.00"))
        self.assertEqual(basket.total_incl_tax, D("10.68"))
        self.assertEqual(basket.total_tax, D("0.68"))

        purchase_info = basket.all_lines()[0].purchase_info
        self.assertEqual(purchase_info.price.excl_tax, D("10.00"))
        self.assertEqual(purchase_info.price.incl_tax, D("10.68"))
        self.assertEqual(purchase_info.price.tax, D("0.68"))

        details = purchase_info.price.taxation_details
        self.assertEqual(len(details), 2)
        self.assertEqual(details[0].authority_name, "OHIO, STATE OF")
        self.assertEqual(details[0].tax_name, "STATE SALES TAX-GENERAL MERCHANDISE")
        self.assertEqual(details[0].tax_applied, D("0.58"))
        self.assertEqual(details[0].fee_applied, D("0.00"))

        self.assertTrue(shipping_charge.is_tax_known)
        self.assertEqual(shipping_charge.excl_tax, D("14.99"))
        self.assertEqual(shipping_charge.incl_tax, D("16.3203625"))
        self.assertEqual(len(shipping_charge.components[0].taxation_details), 3)
        self.assertEqual(
            shipping_charge.components[0].taxation_details[0].authority_name,
            "NEW YORK, STATE OF",
        )
        self.assertEqual(
            shipping_charge.components[0].taxation_details[0].tax_name,
            "STATE SALES TAX-GENERAL MERCHANDISE",
        )
        self.assertEqual(
            shipping_charge.components[0].taxation_details[0].tax_applied, D("0.5996")
        )
        self.assertEqual(
            shipping_charge.components[0].taxation_details[0].fee_applied, D("0.00")
        )

    def test_apply_taxes_nine_digits_postal_code(self):
        basket = self.prepare_basket_full_zip()
        to_address = self.get_to_address_ohio_full_zip()
        shipping_charge = self.get_shipping_charge()

        CCHTaxCalculator().apply_taxes(to_address, basket, shipping_charge)

        self.assertTrue(basket.is_tax_known)
        print("basket: %s" % basket)
        self.assertEqual(basket.total_excl_tax, D("10.00"))
        self.assertEqual(basket.total_incl_tax, D("10.73"))
        self.assertEqual(basket.total_tax, D("0.73"))

        purchase_info = basket.all_lines()[0].purchase_info
        self.assertEqual(purchase_info.price.excl_tax, D("10.00"))
        self.assertEqual(purchase_info.price.incl_tax, D("10.73"))
        self.assertEqual(purchase_info.price.tax, D("0.73"))

        details = purchase_info.price.taxation_details
        self.assertEqual(len(details), 2)
        self.assertEqual(details[0].authority_name, "OHIO, STATE OF")
        self.assertEqual(details[0].tax_name, "STATE SALES TAX-GENERAL MERCHANDISE")
        self.assertEqual(details[0].tax_applied, D("0.58"))
        self.assertEqual(details[0].fee_applied, D("0.00"))

        self.assertTrue(shipping_charge.is_tax_known)
        self.assertEqual(shipping_charge.excl_tax, D("14.99"))
        self.assertEqual(shipping_charge.incl_tax, D("16.3203625"))
        self.assertEqual(len(shipping_charge.components[0].taxation_details), 3)
        self.assertEqual(
            shipping_charge.components[0].taxation_details[0].authority_name,
            "NEW YORK, STATE OF",
        )
        self.assertEqual(
            shipping_charge.components[0].taxation_details[0].tax_name,
            "STATE SALES TAX-GENERAL MERCHANDISE",
        )
        self.assertEqual(
            shipping_charge.components[0].taxation_details[0].tax_applied, D("0.5996")
        )
        self.assertEqual(
            shipping_charge.components[0].taxation_details[0].fee_applied, D("0.00")
        )
