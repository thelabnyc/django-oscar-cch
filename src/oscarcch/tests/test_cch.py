from decimal import Decimal as D
from freezegun import freeze_time
from soap.http import HttpTransport
from oscar.core.loading import get_model, get_class
from oscar.test import factories
from .base import BaseTest
from .base import p
import mock
import requests

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


class CCHTaxCalculatorTest(BaseTest):

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @mock.patch('soap.get_transport')
    def test_apply_taxes_normal(self, get_transport):
        basket = self.prepare_basket()
        to_address = self.get_to_address()

        def test_request(request):
            self.assertNodeText(request.message, p('Body/CalculateRequest/EntityID'), 'TESTSANDBOX')
            self.assertNodeText(request.message, p('Body/CalculateRequest/DivisionID'), '42')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/CustomerType'), '08')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/InvoiceDate'), '2016-04-13T12:14:44.018599-04:00')
            self.assertNodeCount(request.message, p('Body/CalculateRequest/order/LineItems/LineItem'), 1)
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/AvgUnitPrice'), '10.00000')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/ID'), str(basket.all_lines()[0].id))
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/City'), 'Anchorage')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/CountryCode'), 'US')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/Line1'), '221 Baker st')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/Line2'), 'B')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/PostalCode'), '99501')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/StateOrProvince'), 'AK')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/City'), 'Brooklyn')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/CountryCode'), 'US')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/Line1'), '123 Evergreen Terrace')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/Line2'), 'Apt #1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/PostalCode'), '11201')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/StateOrProvince'), 'NY')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/Quantity'), '1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/SKU'), 'ABC123')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/ProviderType'), '70')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/SourceSystem'), 'Oscar')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/TestTransaction'), 'true')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/TransactionID'), '0')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/TransactionType'), '01')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/finalize'), 'false')
        resp = self._get_cch_response_normal( basket.all_lines()[0].id )
        get_transport.return_value = self._build_transport_with_reply(resp, test_request=test_request)

        self.assertFalse(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))

        CCHTaxCalculator().apply_taxes(basket, to_address)

        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))
        self.assertEqual(basket.total_incl_tax, D('10.89'))
        self.assertEqual(basket.total_tax, D('0.89'))

        purchase_info = basket.all_lines()[0].purchase_info
        self.assertEqual(purchase_info.price.excl_tax, D('10.00'))
        self.assertEqual(purchase_info.price.incl_tax, D('10.89'))
        self.assertEqual(purchase_info.price.tax, D('0.89'))

        details = purchase_info.price.taxation_details
        self.assertEqual(len(details), 3)
        self.assertEqual(details[0].authority_name, 'NEW YORK, STATE OF')
        self.assertEqual(details[0].tax_name, 'STATE SALES TAX-GENERAL MERCHANDISE')
        self.assertEqual(details[0].tax_applied, D('0.40'))
        self.assertEqual(details[0].fee_applied, D('0.00'))


    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @mock.patch('soap.get_transport')
    def test_apply_taxes_read_timeout(self, get_transport):
        basket = self.prepare_basket()
        to_address = self.get_to_address()

        # Make requests throw a ReadTimeout
        def raise_error(*args, **kwargs):
            raise requests.exceptions.ReadTimeout()
        transport = HttpTransport()
        transport.session.post = mock.MagicMock(side_effect=raise_error)
        get_transport.return_value = transport

        self.assertFalse(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))

        with self.assertRaises(requests.exceptions.ReadTimeout):
            CCHTaxCalculator().apply_taxes(basket, to_address)


    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @mock.patch('soap.get_transport')
    def test_apply_taxes_read_timeout_retried(self, get_transport):
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        closured = {'i': 0}

        # Make requests throw a ReadTimeout, but only the first time.
        def raise_error(*args, **kwargs):
            if closured['i'] > 0:
                resp = mock.MagicMock()
                resp.headers = {}
                resp.content = self._get_cch_response_normal( basket.all_lines()[0].id )
                return resp
            closured['i'] += 1
            raise requests.exceptions.ReadTimeout()
        transport = HttpTransport()
        transport.session.post = mock.MagicMock(side_effect=raise_error)
        get_transport.return_value = transport

        self.assertFalse(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))

        CCHTaxCalculator().apply_taxes(basket, to_address)

        self.assertEqual(transport.session.post.call_count, 2)

        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))
        self.assertEqual(basket.total_incl_tax, D('10.89'))
        self.assertEqual(basket.total_tax, D('0.89'))


    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @mock.patch('soap.get_transport')
    def test_apply_taxes_after_discount(self, get_transport):
        basket = self.prepare_basket()
        to_address = self.get_to_address()

        # Make an offer to apply to the basket
        rng = Range.objects.create(name='Some products', includes_all_products=True)
        condition = Condition.objects.create(range=rng, type=Condition.VALUE, value=D('0.01'))
        benefit = Benefit.objects.create(range=rng, type=Benefit.PERCENTAGE, value=D('50.00'))
        ConditionalOffer.objects.create(name='My Discount', condition=condition, benefit=benefit)

        # Apply offers to basket
        self.assertEqual(basket.total_excl_tax, D('10.00'))
        Applicator().apply(basket)
        self.assertEqual(basket.total_excl_tax, D('5.00'))

        def test_request(request):
            self.assertNodeText(request.message, p('Body/CalculateRequest/EntityID'), 'TESTSANDBOX')
            self.assertNodeText(request.message, p('Body/CalculateRequest/DivisionID'), '42')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/CustomerType'), '08')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/InvoiceDate'), '2016-04-13T12:14:44.018599-04:00')
            self.assertNodeCount(request.message, p('Body/CalculateRequest/order/LineItems/LineItem'), 1)
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/AvgUnitPrice'), '5.00000')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/ID'), str(basket.all_lines()[0].id))
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/City'), 'Anchorage')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/CountryCode'), 'US')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/Line1'), '221 Baker st')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/Line2'), 'B')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/PostalCode'), '99501')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/StateOrProvince'), 'AK')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/City'), 'Brooklyn')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/CountryCode'), 'US')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/Line1'), '123 Evergreen Terrace')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/Line2'), 'Apt #1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/PostalCode'), '11201')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/StateOrProvince'), 'NY')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/Quantity'), '1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/SKU'), 'ABC123')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/ProviderType'), '70')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/SourceSystem'), 'Oscar')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/TestTransaction'), 'true')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/TransactionID'), '0')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/TransactionType'), '01')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/finalize'), 'false')
        resp = self._get_cch_response_normal( basket.all_lines()[0].id )
        get_transport.return_value = self._build_transport_with_reply(resp, test_request=test_request)

        self.assertFalse(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('5.00'))

        CCHTaxCalculator().apply_taxes(basket, to_address)

        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('5.00'))
        self.assertEqual(basket.total_incl_tax, D('5.89'))
        self.assertEqual(basket.total_tax, D('0.89'))

        purchase_info = basket.all_lines()[0].purchase_info
        self.assertEqual(purchase_info.price.excl_tax, D('10.00'))
        self.assertEqual(purchase_info.price.incl_tax, D('10.89'))
        self.assertEqual(purchase_info.price.tax, D('0.89'))

        details = purchase_info.price.taxation_details
        self.assertEqual(len(details), 3)
        self.assertEqual(details[0].authority_name, 'NEW YORK, STATE OF')
        self.assertEqual(details[0].tax_name, 'STATE SALES TAX-GENERAL MERCHANDISE')
        self.assertEqual(details[0].tax_applied, D('0.40'))
        self.assertEqual(details[0].fee_applied, D('0.00'))


    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @mock.patch('soap.get_transport')
    def test_custom_quantity(self, get_transport):
        basket = self.prepare_basket()
        to_address = self.get_to_address()

        # Set a custom cch_quantity property
        for basket_line in basket.all_lines():
            basket_line.cch_quantity = 3

        def test_request(request):
            self.assertNodeCount(request.message, p('Body/CalculateRequest/order/LineItems/LineItem'), 1)
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/AvgUnitPrice'), '3.33333')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/ID'), str(basket_line.id))
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/Quantity'), '3')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/SKU'), 'ABC123')

        resp = self._get_cch_response_normal(basket_line.id)
        get_transport.return_value = self._build_transport_with_reply(resp, test_request=test_request)

        self.assertFalse(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))

        CCHTaxCalculator().apply_taxes(basket, to_address)

        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))
        self.assertEqual(basket.total_incl_tax, D('10.89'))
        self.assertEqual(basket.total_tax, D('0.89'))


    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @mock.patch('soap.get_transport')
    def test_apply_taxes_custom_sku(self, get_transport):
        basket = Basket()
        basket.strategy = USStrategy()

        product = factories.create_product(attributes={
            'cch_product_sku': 'CCH Product SKU',
        })
        product.attr.cch_product_sku = 'XYZ456'
        product.save()
        record = factories.create_stockrecord(
            currency='USD',
            product=product,
            price_excl_tax=D('10.00'))
        factories.create_purchase_info(record)
        basket.add(product)

        from_address = PartnerAddress()
        from_address.line1 = '221 Baker st'
        from_address.line2 = 'B'
        from_address.line4 = 'Anchorage'
        from_address.state = 'AK'
        from_address.postcode = '99501'
        from_address.country = Country.objects.get(pk='US')
        from_address.partner = record.partner
        from_address.save()

        to_address = self.get_to_address()

        def test_request(request):
            self.assertNodeText(request.message, p('Body/CalculateRequest/EntityID'), 'TESTSANDBOX')
            self.assertNodeText(request.message, p('Body/CalculateRequest/DivisionID'), '42')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/CustomerType'), '08')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/InvoiceDate'), '2016-04-13T12:14:44.018599-04:00')
            self.assertNodeCount(request.message, p('Body/CalculateRequest/order/LineItems/LineItem'), 1)
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/AvgUnitPrice'), '10.00000')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/ID'), str(basket.all_lines()[0].id))
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/City'), 'Anchorage')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/CountryCode'), 'US')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/Line1'), '221 Baker st')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/Line2'), 'B')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/PostalCode'), '99501')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/StateOrProvince'), 'AK')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/City'), 'Brooklyn')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/CountryCode'), 'US')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/Line1'), '123 Evergreen Terrace')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/Line2'), 'Apt #1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/PostalCode'), '11201')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/StateOrProvince'), 'NY')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/Quantity'), '1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/SKU'), 'XYZ456')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/ProviderType'), '70')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/SourceSystem'), 'Oscar')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/TestTransaction'), 'true')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/TransactionID'), '0')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/TransactionType'), '01')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/finalize'), 'false')
        resp = self._get_cch_response_normal( basket.all_lines()[0].id )
        get_transport.return_value = self._build_transport_with_reply(resp, test_request=test_request)

        self.assertFalse(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))

        CCHTaxCalculator().apply_taxes(basket, to_address)

        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))
        self.assertEqual(basket.total_incl_tax, D('10.89'))
        self.assertEqual(basket.total_tax, D('0.89'))

        purchase_info = basket.all_lines()[0].purchase_info
        self.assertEqual(purchase_info.price.excl_tax, D('10.00'))
        self.assertEqual(purchase_info.price.incl_tax, D('10.89'))
        self.assertEqual(purchase_info.price.tax, D('0.89'))


    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @mock.patch('soap.get_transport')
    def test_apply_taxes_custom_sku_empty(self, get_transport):
        basket = Basket()
        basket.strategy = USStrategy()

        product = factories.create_product(attributes={
            'cch_product_sku': 'CCH Product SKU',
        })
        product.attr.cch_product_sku = ''
        product.save()
        record = factories.create_stockrecord(
            currency='USD',
            product=product,
            price_excl_tax=D('10.00'))
        factories.create_purchase_info(record)
        basket.add(product)

        from_address = PartnerAddress()
        from_address.line1 = '221 Baker st'
        from_address.line2 = 'B'
        from_address.line4 = 'Anchorage'
        from_address.state = 'AK'
        from_address.postcode = '99501'
        from_address.country = Country.objects.get(pk='US')
        from_address.partner = record.partner
        from_address.save()

        to_address = self.get_to_address()

        def test_request(request):
            self.assertNodeText(request.message, p('Body/CalculateRequest/EntityID'), 'TESTSANDBOX')
            self.assertNodeText(request.message, p('Body/CalculateRequest/DivisionID'), '42')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/CustomerType'), '08')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/InvoiceDate'), '2016-04-13T12:14:44.018599-04:00')
            self.assertNodeCount(request.message, p('Body/CalculateRequest/order/LineItems/LineItem'), 1)
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/AvgUnitPrice'), '10.00000')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/ID'), str(basket.all_lines()[0].id))
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/City'), 'Anchorage')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/CountryCode'), 'US')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/Line1'), '221 Baker st')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/Line2'), 'B')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/PostalCode'), '99501')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/StateOrProvince'), 'AK')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/City'), 'Brooklyn')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/CountryCode'), 'US')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/Line1'), '123 Evergreen Terrace')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/Line2'), 'Apt #1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/PostalCode'), '11201')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/StateOrProvince'), 'NY')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/Quantity'), '1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/SKU'), 'ABC123')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/ProviderType'), '70')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/SourceSystem'), 'Oscar')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/TestTransaction'), 'true')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/TransactionID'), '0')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/TransactionType'), '01')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/finalize'), 'false')
        resp = self._get_cch_response_normal( basket.all_lines()[0].id )
        get_transport.return_value = self._build_transport_with_reply(resp, test_request=test_request)

        self.assertFalse(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))

        CCHTaxCalculator().apply_taxes(basket, to_address)

        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))
        self.assertEqual(basket.total_incl_tax, D('10.89'))
        self.assertEqual(basket.total_tax, D('0.89'))

        purchase_info = basket.all_lines()[0].purchase_info
        self.assertEqual(purchase_info.price.excl_tax, D('10.00'))
        self.assertEqual(purchase_info.price.incl_tax, D('10.89'))
        self.assertEqual(purchase_info.price.tax, D('0.89'))


    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @mock.patch('soap.get_transport')
    def test_apply_taxes_custom_product_data(self, get_transport):
        basket = Basket()
        basket.strategy = USStrategy()

        product = factories.create_product(attributes={
            'cch_product_group': 'CCH Product Item',
            'cch_product_item': 'CCH Product Group',
        })
        product.attr.cch_product_group = 'MyGroup'
        product.attr.cch_product_item = 'MyItem'
        product.save()
        record = factories.create_stockrecord(
            currency='USD',
            product=product,
            price_excl_tax=D('10.00'))
        factories.create_purchase_info(record)
        basket.add(product)

        from_address = PartnerAddress()
        from_address.line1 = '221 Baker st'
        from_address.line2 = 'B'
        from_address.line4 = 'Anchorage'
        from_address.state = 'AK'
        from_address.postcode = '99501'
        from_address.country = Country.objects.get(pk='US')
        from_address.partner = record.partner
        from_address.save()

        to_address = self.get_to_address()

        def test_request(request):
            self.assertNodeText(request.message, p('Body/CalculateRequest/EntityID'), 'TESTSANDBOX')
            self.assertNodeText(request.message, p('Body/CalculateRequest/DivisionID'), '42')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/CustomerType'), '08')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/InvoiceDate'), '2016-04-13T12:14:44.018599-04:00')
            self.assertNodeCount(request.message, p('Body/CalculateRequest/order/LineItems/LineItem'), 1)
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/AvgUnitPrice'), '10.00000')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/ID'), str(basket.all_lines()[0].id))
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/City'), 'Anchorage')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/CountryCode'), 'US')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/Line1'), '221 Baker st')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/Line2'), 'B')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/PostalCode'), '99501')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/StateOrProvince'), 'AK')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/City'), 'Brooklyn')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/CountryCode'), 'US')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/Line1'), '123 Evergreen Terrace')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/Line2'), 'Apt #1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/PostalCode'), '11201')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/StateOrProvince'), 'NY')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/Quantity'), '1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/SKU'), 'ABC123')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/ProductInfo/ProductGroup'), 'MyGroup')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/ProductInfo/ProductItem'), 'MyItem')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/ProviderType'), '70')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/SourceSystem'), 'Oscar')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/TestTransaction'), 'true')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/TransactionID'), '0')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/TransactionType'), '01')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/finalize'), 'false')
        resp = self._get_cch_response_normal( basket.all_lines()[0].id )
        get_transport.return_value = self._build_transport_with_reply(resp, test_request=test_request)

        self.assertFalse(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))

        CCHTaxCalculator().apply_taxes(basket, to_address)

        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))
        self.assertEqual(basket.total_incl_tax, D('10.89'))
        self.assertEqual(basket.total_tax, D('0.89'))

        purchase_info = basket.all_lines()[0].purchase_info
        self.assertEqual(purchase_info.price.excl_tax, D('10.00'))
        self.assertEqual(purchase_info.price.incl_tax, D('10.89'))
        self.assertEqual(purchase_info.price.tax, D('0.89'))


    @mock.patch('soap.get_transport')
    def test_truncate_postal_code(self, get_transport):
        basket = self.prepare_basket()
        to_address = self.get_to_address()

        def test_request(request):
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipFromAddress/PostalCode'), '99501')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/NexusInfo/ShipToAddress/PostalCode'), '11201')
        resp = self._get_cch_response_normal( basket.all_lines()[0].id )
        get_transport.return_value = self._build_transport_with_reply(resp, test_request=test_request)

        self.assertFalse(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))

        from_address = basket.all_lines()[0].stockrecord.partner.primary_address
        from_address.postcode = '99501-1234'
        from_address.save()

        to_address.postcode = '11201-9876'
        to_address.save()

        CCHTaxCalculator().apply_taxes(basket, to_address)

        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))
        self.assertEqual(basket.total_incl_tax, D('10.89'))


    @mock.patch('soap.get_transport')
    def test_apply_taxes_repeatedly(self, get_transport):
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        resp = self._get_cch_response_normal( basket.all_lines()[0].id )
        get_transport.return_value = self._build_transport_with_reply(resp)

        def assert_taxes_are_correct():
            self.assertTrue(basket.is_tax_known)
            self.assertEqual(basket.total_excl_tax, D('10.00'))
            self.assertEqual(basket.total_incl_tax, D('10.89'))
            self.assertEqual(basket.total_tax, D('0.89'))

            purchase_info = basket.all_lines()[0].purchase_info
            self.assertEqual(purchase_info.price.excl_tax, D('10.00'))
            self.assertEqual(purchase_info.price.incl_tax, D('10.89'))
            self.assertEqual(purchase_info.price.tax, D('0.89'))

            details = purchase_info.price.taxation_details
            self.assertEqual(len(details), 3)
            self.assertEqual(details[0].authority_name, 'NEW YORK, STATE OF')
            self.assertEqual(details[0].tax_name, 'STATE SALES TAX-GENERAL MERCHANDISE')
            self.assertEqual(details[0].tax_applied, D('0.40'))
            self.assertEqual(details[0].fee_applied, D('0.00'))

        self.assertFalse(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))

        CCHTaxCalculator().apply_taxes(basket, to_address)
        assert_taxes_are_correct()

        CCHTaxCalculator().apply_taxes(basket, to_address)
        assert_taxes_are_correct()

        CCHTaxCalculator().apply_taxes(basket, to_address)
        assert_taxes_are_correct()


    @mock.patch('soap.get_transport')
    def test_apply_taxes_tax_free(self, get_transport):
        basket = self.prepare_basket()
        to_address = self.get_to_address()

        resp = self._get_cch_response_empty()
        get_transport.return_value = self._build_transport_with_reply(resp)

        self.assertFalse(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))

        CCHTaxCalculator().apply_taxes(basket, to_address)

        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))
        self.assertEqual(basket.total_incl_tax, D('10.00'))
        self.assertEqual(basket.total_tax, D('0.00'))

        purchase_info = basket.all_lines()[0].purchase_info
        self.assertEqual(purchase_info.price.excl_tax, D('10.00'))
        self.assertEqual(purchase_info.price.incl_tax, D('10.00'))
        self.assertEqual(purchase_info.price.tax, D('0.00'))

        details = purchase_info.price.taxation_details
        self.assertEqual(len(details), 0)


    @mock.patch('soap.get_transport')
    def test_estimate_taxes(self, get_transport):
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        resp = self._get_cch_response_normal( basket.all_lines()[0].id )
        transport = self._build_transport_with_reply(resp)
        get_transport.return_value = transport

        def assert_taxes_are_correct(b):
            self.assertTrue(b.is_tax_known)
            self.assertEqual(b.total_excl_tax, D('10.00'))
            self.assertEqual(b.total_incl_tax, D('10.89'))
            self.assertEqual(b.total_tax, D('0.89'))

            purchase_info = b.all_lines()[0].purchase_info
            self.assertEqual(purchase_info.price.excl_tax, D('10.00'))
            self.assertEqual(purchase_info.price.incl_tax, D('10.89'))
            self.assertEqual(purchase_info.price.tax, D('0.89'))

            details = purchase_info.price.taxation_details
            self.assertEqual(len(details), 3)
            self.assertEqual(details[0].authority_name, 'NEW YORK, STATE OF')
            self.assertEqual(details[0].tax_name, 'STATE SALES TAX-GENERAL MERCHANDISE')
            self.assertEqual(details[0].tax_applied, D('0.40'))
            self.assertEqual(details[0].fee_applied, D('0.00'))

        self.assertFalse(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))

        self.assertEqual(transport.send.call_count, 0)
        b1 = CCHTaxCalculator().estimate_taxes(basket, to_address)
        self.assertEqual(transport.send.call_count, 1)
        assert_taxes_are_correct(b1)

        b2 = CCHTaxCalculator().estimate_taxes(basket, to_address)
        self.assertEqual(transport.send.call_count, 2)
        assert_taxes_are_correct(b2)

        b3 = CCHTaxCalculator().estimate_taxes(basket, to_address)
        self.assertEqual(transport.send.call_count, 3)
        assert_taxes_are_correct(b3)

        basket.save()

        b4 = CCHTaxCalculator().estimate_taxes(basket, to_address)
        self.assertEqual(transport.send.call_count, 4)
        assert_taxes_are_correct(b4)


    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @mock.patch('soap.get_transport')
    def test_apply_taxes_zero_qty_line(self, get_transport):
        basket = self.prepare_basket(lines=2)
        to_address = self.get_to_address()

        basket.add_product(basket.all_lines()[0].product, -1)

        def test_request(request):
            self.assertNodeCount(request.message, p('Body/CalculateRequest/order/LineItems/LineItem'), 1)
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem/AvgUnitPrice'), '10.00000')

        resp = self._get_cch_response_normal(basket.all_lines()[1].id)
        get_transport.return_value = self._build_transport_with_reply(resp, test_request=test_request)

        self.assertFalse(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))

        CCHTaxCalculator().apply_taxes(basket, to_address)

        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))
        self.assertEqual(basket.total_incl_tax, D('10.89'))
        self.assertEqual(basket.total_tax, D('0.89'))

        self.assertEqual(len(basket.all_lines()), 2)
