from django.test import TestCase
from oscar.core.loading import get_model, get_class
from oscar.test import factories
from decimal import Decimal as D

from cch.calculator import CCHTaxCalculator

Basket = get_model('basket', 'Basket')
ShippingAddress = get_model('order', 'ShippingAddress')
Country = get_model('address', 'Country')
USStrategy = get_class('partner.strategy', 'US')


class CCHTaxCalculatorTest(TestCase):
    def setUp(self):
        Country.objects.create(
            iso_3166_1_a2='US',
            is_shipping_country=True,
            iso_3166_1_a3='USA',
            iso_3166_1_numeric='840',
            display_order=0,
            name="United States of America",
            printable_name="United States")

    def test_apply_taxes(self):
        basket = Basket()
        basket.strategy = USStrategy()
        product = factories.create_product()
        record = factories.create_stockrecord(
            currency='USD',
            product=product,
            price_excl_tax=D('10.00'))
        factories.create_purchase_info(record)
        basket.add(product)

        self.assertFalse(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))

        address = ShippingAddress()
        address.line4 = 'Brooklyn'
        address.state = 'NY'
        address.postcode = '11201'
        address.country = Country.objects.get(pk='US')

        cch = CCHTaxCalculator()
        cch.apply_taxes(basket, address)

        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))
        self.assertTrue(basket.total_incl_tax > D('10.00'))
        self.assertTrue(basket.total_tax > D('0.00'))
