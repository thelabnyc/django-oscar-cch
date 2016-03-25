from django.test import TestCase
from oscar.core.loading import get_model, get_class
from oscar.test import factories
from decimal import Decimal as D

Basket = get_model('basket', 'Basket')
ShippingAddress = get_model('order', 'ShippingAddress')
Country = get_model('address', 'Country')
USStrategy = get_class('partner.strategy', 'US')


class PersistCCHDetailsTest(TestCase):
    def setUp(self):
        Country.objects.create(
            iso_3166_1_a2='US',
            is_shipping_country=True,
            iso_3166_1_a3='USA',
            iso_3166_1_numeric='840',
            display_order=0,
            name="United States of America",
            printable_name="United States")

    def make_basket(self):
        # Create a basket to convert into an order
        basket = Basket()
        basket.strategy = USStrategy()
        product = factories.create_product()
        record = factories.create_stockrecord(
            currency='USD',
            product=product,
            price_excl_tax=D('10.00'))
        factories.create_purchase_info(record)
        basket.add(product)
        return basket

    def test_persist_taxation_details(self):
        basket = self.make_basket()
        # Create a shipping address
        address = ShippingAddress()
        address.line4 = 'Brooklyn'
        address.state = 'NY'
        address.postcode = '11201'
        address.country = Country.objects.get(pk='US')
        address.save()

        # This should call CCH and save tax details in the DB
        order = factories.create_order(basket=basket, shipping_address=address)

        # Make sure we have an order taxation object
        self.assertTrue(order.taxation.transaction_id > 0)
        self.assertEqual(order.taxation.transaction_status, 4)
        self.assertTrue(order.taxation.total_tax_applied > 0)

        # Make sure we have an line taxation objects
        for line in order.lines.all():
            self.assertEqual(line.taxation.country_code, 'US')
            self.assertEqual(line.taxation.state_code, 'NY')
            self.assertTrue(line.taxation.total_tax_applied > 0)
            self.assertTrue(line.taxation.details.count() > 0)
            for detail in line.taxation.details.all():
                self.assertIn('AuthorityName', detail.data)
                self.assertIn('TaxName', detail.data)
                self.assertIn('TaxRate', detail.data)
                self.assertTrue(float(detail.data['TaxRate']) > 0)
                self.assertIn('TaxableAmount', detail.data)
                self.assertIn('TaxableQuantity', detail.data)

    def test_persist_taxation_details_when_zero(self):
        """ Same as above but with 0 tax """
        basket = self.make_basket()

        # Create a shipping address
        address = ShippingAddress()
        address.line4 = 'Anchorage'
        address.state = 'AK'
        address.postcode = '99507'
        address.country = Country.objects.get(pk='US')
        address.save()

        # This should call CCH and save tax details in the DB
        order = factories.create_order(basket=basket, shipping_address=address)
