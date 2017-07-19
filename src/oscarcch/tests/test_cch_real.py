from decimal import Decimal as D
from oscar.core.loading import get_model, get_class
from .base import BaseTest
import unittest


Basket = get_model('basket', 'Basket')
ShippingAddress = get_model('order', 'ShippingAddress')
Country = get_model('address', 'Country')
PartnerAddress = get_model('partner', 'PartnerAddress')
Range = get_model('offer', 'Range')
Benefit = get_model('offer', 'Benefit')
Condition = get_model('offer', 'Condition')
ConditionalOffer = get_model('offer', 'ConditionalOffer')

USStrategy = get_class('partner.strategy', 'US')
Applicator = get_class('offer.applicator', 'Applicator')
CCHTaxCalculator = get_class('oscarcch.calculator', 'CCHTaxCalculator')


@unittest.skip("Disabled because it uses real cch")
class CCHTaxCalculatorRealTest(BaseTest):


    def test_apply_taxes_five_digits_postal_code(self):
        basket = self.prepare_basket_full_zip()
        to_address = self.get_to_address_ohio_short_zip()

        CCHTaxCalculator().apply_taxes(basket, to_address)

        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))
        self.assertEqual(basket.total_incl_tax, D('10.68'))
        self.assertEqual(basket.total_tax, D('0.68'))

        purchase_info = basket.all_lines()[0].purchase_info
        self.assertEqual(purchase_info.price.excl_tax, D('10.00'))
        self.assertEqual(purchase_info.price.incl_tax, D('10.68'))
        self.assertEqual(purchase_info.price.tax, D('0.68'))

        details = purchase_info.price.taxation_details
        self.assertEqual(len(details), 2)
        self.assertEqual(details[0].authority_name, 'OHIO, STATE OF')
        self.assertEqual(details[0].tax_name, 'STATE SALES TAX-GENERAL MERCHANDISE')
        self.assertEqual(details[0].tax_applied, D('0.58'))
        self.assertEqual(details[0].fee_applied, D('0.00'))

    def test_apply_taxes_nine_digits_postal_code(self):
        basket = self.prepare_basket_full_zip()
        to_address = self.get_to_address_ohio_full_zip()

        CCHTaxCalculator().apply_taxes(basket, to_address)

        self.assertTrue(basket.is_tax_known)
        print("basket: %s" % basket)
        self.assertEqual(basket.total_excl_tax, D('10.00'))
        self.assertEqual(basket.total_incl_tax, D('10.73'))
        self.assertEqual(basket.total_tax, D('0.73'))

        purchase_info = basket.all_lines()[0].purchase_info
        self.assertEqual(purchase_info.price.excl_tax, D('10.00'))
        self.assertEqual(purchase_info.price.incl_tax, D('10.73'))
        self.assertEqual(purchase_info.price.tax, D('0.73'))

        details = purchase_info.price.taxation_details
        self.assertEqual(len(details), 2)
        self.assertEqual(details[0].authority_name, 'OHIO, STATE OF')
        self.assertEqual(details[0].tax_name, 'STATE SALES TAX-GENERAL MERCHANDISE')
        self.assertEqual(details[0].tax_applied, D('0.58'))
        self.assertEqual(details[0].fee_applied, D('0.00'))
