from decimal import Decimal as D
from oscar.core.loading import get_model, get_class
from oscar.test import factories
from .base import BaseTest
import mock

Basket = get_model('basket', 'Basket')
ShippingAddress = get_model('order', 'ShippingAddress')
Country = get_model('address', 'Country')
USStrategy = get_class('partner.strategy', 'US')


class PersistCCHDetailsTest(BaseTest):
    @mock.patch('soap.get_transport')
    def test_persist_taxation_details(self, get_transport):
        """Place an order with normal taxes"""
        basket = self.prepare_basket()
        to_address = self.get_to_address()

        resp = self._get_cch_response_normal( basket.all_lines()[0].id )
        get_transport.return_value = self._build_transport_with_reply(resp)

        # This should call CCH and save tax details in the DB
        order = factories.create_order(basket=basket, shipping_address=to_address)

        # Make sure we have an order taxation object
        self.assertEqual(order.taxation.transaction_id, 40043)
        self.assertEqual(order.taxation.transaction_status, 4)
        self.assertEqual(order.taxation.total_tax_applied, D('0.89'))

        # Make sure we have an line taxation objects
        for line in order.lines.all():
            self.assertEqual(line.taxation.country_code, 'US')
            self.assertEqual(line.taxation.state_code, 'NY')
            self.assertEqual(line.taxation.total_tax_applied, D('0.89'))
            self.assertEqual(line.taxation.details.count(), 3)
            for detail in line.taxation.details.all():
                self.assertIn('AuthorityName', detail.data)
                self.assertIn('TaxName', detail.data)
                self.assertIn('TaxRate', detail.data)
                self.assertTrue(float(detail.data['TaxRate']) > 0)
                self.assertIn('TaxableAmount', detail.data)
                self.assertIn('TaxableQuantity', detail.data)

    @mock.patch('soap.get_transport')
    def test_persist_taxation_details_when_zero(self, get_transport):
        """Place a tax free order"""
        basket = self.prepare_basket()
        to_address = self.get_to_address()

        resp = self._get_cch_response_empty()
        get_transport.return_value = self._build_transport_with_reply(resp)

        # This should call CCH and save tax details in the DB
        order = factories.create_order(basket=basket, shipping_address=to_address)

        # Make sure we have an order taxation object
        self.assertEqual(order.taxation.transaction_id, 40043)
        self.assertEqual(order.taxation.transaction_status, 4)
        self.assertEqual(order.taxation.total_tax_applied, D('0.00'))

        # Make sure we have an line taxation objects
        for line in order.lines.all():
            self.assertFalse(hasattr(line, 'taxation'))
