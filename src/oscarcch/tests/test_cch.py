from unittest import mock
from decimal import Decimal as D
from freezegun import freeze_time
from oscar.core.loading import get_model, get_class
from oscar.test import factories
from ..calculator import CCHTaxCalculator
from ..prices import ShippingCharge
from .base import BaseTest
from .base import p
import requests
import pybreaker

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


class CCHTaxCalculatorTest(BaseTest):

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @mock.patch('soap.get_transport')
    def test_apply_taxes_normal(self, get_transport):
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        shipping_charge = self.get_shipping_charge()

        def test_request(request):
            self.assertNodeText(request.message, p('Body/CalculateRequest/EntityID'), 'TESTSANDBOX')
            self.assertNodeText(request.message, p('Body/CalculateRequest/DivisionID'), '42')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/CustomerType'), '08')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/InvoiceDate'), '2016-04-13T12:14:44.018599-04:00')
            self.assertNodeCount(request.message, p('Body/CalculateRequest/order/LineItems/LineItem'), 2)
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/AvgUnitPrice'), '10.00000')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/ID'), str(basket.all_lines()[0].id))
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/City'), 'Anchorage')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/CountryCode'), 'US')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/Line1'), '221 Baker st')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/Line2'), 'B')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/PostalCode'), '99501')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/StateOrProvince'), 'AK')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/City'), 'Brooklyn')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/CountryCode'), 'US')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/Line1'), '123 Evergreen Terrace')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/Line2'), 'Apt #1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/PostalCode'), '11201')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/StateOrProvince'), 'NY')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/Quantity'), '1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/SKU'), 'ABC123')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[2]/AvgUnitPrice'), '14.99000')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[2]/ID'), 'shipping:PARCEL:0')  # NOQA
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[2]/NexusInfo/ShipToAddress/City'), 'Brooklyn')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[2]/NexusInfo/ShipToAddress/CountryCode'), 'US')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[2]/NexusInfo/ShipToAddress/Line1'), '123 Evergreen Terrace')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[2]/NexusInfo/ShipToAddress/Line2'), 'Apt #1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[2]/NexusInfo/ShipToAddress/PostalCode'), '11201')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[2]/NexusInfo/ShipToAddress/StateOrProvince'), 'NY')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[2]/Quantity'), '1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[2]/SKU'), 'PARCEL')
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

        self.assertFalse(shipping_charge.is_tax_known)
        self.assertEqual(shipping_charge.excl_tax, D('14.99'))

        CCHTaxCalculator().apply_taxes(to_address, basket, shipping_charge)

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

        self.assertTrue(shipping_charge.is_tax_known)
        self.assertEqual(shipping_charge.excl_tax, D('14.99'))
        self.assertEqual(shipping_charge.incl_tax, D('16.3203625'))
        self.assertEqual(len(shipping_charge.components[0].taxation_details), 3)
        self.assertEqual(shipping_charge.components[0].taxation_details[0].authority_name, 'NEW YORK, STATE OF')
        self.assertEqual(shipping_charge.components[0].taxation_details[0].tax_name, 'STATE SALES TAX-GENERAL MERCHANDISE')
        self.assertEqual(shipping_charge.components[0].taxation_details[0].tax_applied, D('0.5996'))
        self.assertEqual(shipping_charge.components[0].taxation_details[0].fee_applied, D('0.00'))


    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @mock.patch('soap.get_transport')
    def test_apply_taxes_basket_only(self, get_transport):
        basket = self.prepare_basket()
        to_address = self.get_to_address()

        def test_request(request):
            self.assertNodeText(request.message, p('Body/CalculateRequest/EntityID'), 'TESTSANDBOX')
            self.assertNodeText(request.message, p('Body/CalculateRequest/DivisionID'), '42')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/CustomerType'), '08')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/InvoiceDate'), '2016-04-13T12:14:44.018599-04:00')
            self.assertNodeCount(request.message, p('Body/CalculateRequest/order/LineItems/LineItem'), 1)
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/AvgUnitPrice'), '10.00000')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/ID'), str(basket.all_lines()[0].id))
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/City'), 'Anchorage')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/CountryCode'), 'US')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/Line1'), '221 Baker st')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/Line2'), 'B')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/PostalCode'), '99501')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/StateOrProvince'), 'AK')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/City'), 'Brooklyn')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/CountryCode'), 'US')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/Line1'), '123 Evergreen Terrace')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/Line2'), 'Apt #1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/PostalCode'), '11201')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/StateOrProvince'), 'NY')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/Quantity'), '1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/SKU'), 'ABC123')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/ProviderType'), '70')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/SourceSystem'), 'Oscar')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/TestTransaction'), 'true')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/TransactionID'), '0')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/TransactionType'), '01')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/finalize'), 'false')

        resp = self._get_cch_response_basket_only( basket.all_lines()[0].id )
        get_transport.return_value = self._build_transport_with_reply(resp, test_request=test_request)

        self.assertFalse(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))

        CCHTaxCalculator().apply_taxes(to_address, basket=basket)

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
    def test_apply_taxes_shipping_only(self, get_transport):
        to_address = self.get_to_address()
        shipping_charge = self.get_shipping_charge()

        def test_request(request):
            self.assertNodeText(request.message, p('Body/CalculateRequest/EntityID'), 'TESTSANDBOX')
            self.assertNodeText(request.message, p('Body/CalculateRequest/DivisionID'), '42')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/CustomerType'), '08')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/InvoiceDate'), '2016-04-13T12:14:44.018599-04:00')
            self.assertNodeCount(request.message, p('Body/CalculateRequest/order/LineItems/LineItem'), 1)
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/AvgUnitPrice'), '14.99000')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/ID'), 'shipping:PARCEL:0')  # NOQA
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/City'), 'Brooklyn')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/CountryCode'), 'US')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/Line1'), '123 Evergreen Terrace')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/Line2'), 'Apt #1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/PostalCode'), '11201')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/StateOrProvince'), 'NY')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/Quantity'), '1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/SKU'), 'PARCEL')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/ProviderType'), '70')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/SourceSystem'), 'Oscar')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/TestTransaction'), 'true')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/TransactionID'), '0')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/TransactionType'), '01')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/finalize'), 'false')

        resp = self._get_cch_response_shipping_only()
        get_transport.return_value = self._build_transport_with_reply(resp, test_request=test_request)

        self.assertFalse(shipping_charge.is_tax_known)
        self.assertEqual(shipping_charge.excl_tax, D('14.99'))

        CCHTaxCalculator().apply_taxes(to_address, shipping_charge=shipping_charge)

        self.assertTrue(shipping_charge.is_tax_known)
        self.assertEqual(shipping_charge.excl_tax, D('14.99'))
        self.assertEqual(shipping_charge.incl_tax, D('16.3203625'))
        self.assertEqual(len(shipping_charge.components[0].taxation_details), 3)
        self.assertEqual(shipping_charge.components[0].taxation_details[0].authority_name, 'NEW YORK, STATE OF')
        self.assertEqual(shipping_charge.components[0].taxation_details[0].tax_name, 'STATE SALES TAX-GENERAL MERCHANDISE')
        self.assertEqual(shipping_charge.components[0].taxation_details[0].tax_applied, D('0.5996'))
        self.assertEqual(shipping_charge.components[0].taxation_details[0].fee_applied, D('0.00'))


    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @mock.patch('soap.get_transport')
    def test_apply_taxes_shipping_only_multiple_skus(self, get_transport):
        to_address = self.get_to_address()

        shipping_charge = ShippingCharge('USD')
        shipping_charge.add_component('FREIGHT', D('100.00'))
        shipping_charge.add_component('UPS', D('20.00'))

        def test_request(request):
            self.assertNodeText(request.message, p('Body/CalculateRequest/EntityID'), 'TESTSANDBOX')
            self.assertNodeText(request.message, p('Body/CalculateRequest/DivisionID'), '42')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/CustomerType'), '08')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/InvoiceDate'), '2016-04-13T12:14:44.018599-04:00')
            self.assertNodeCount(request.message, p('Body/CalculateRequest/order/LineItems/LineItem'), 2)
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/AvgUnitPrice'), '100.00000')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/ID'), 'shipping:FREIGHT:0')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/City'), 'Brooklyn')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/CountryCode'), 'US')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/Line1'), '123 Evergreen Terrace')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/Line2'), 'Apt #1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/PostalCode'), '11201')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/StateOrProvince'), 'NY')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/Quantity'), '1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/SKU'), 'FREIGHT')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[2]/AvgUnitPrice'), '20.00000')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[2]/ID'), 'shipping:UPS:1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[2]/NexusInfo/ShipToAddress/City'), 'Brooklyn')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[2]/NexusInfo/ShipToAddress/CountryCode'), 'US')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[2]/NexusInfo/ShipToAddress/Line1'), '123 Evergreen Terrace')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[2]/NexusInfo/ShipToAddress/Line2'), 'Apt #1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[2]/NexusInfo/ShipToAddress/PostalCode'), '11201')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[2]/NexusInfo/ShipToAddress/StateOrProvince'), 'NY')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[2]/Quantity'), '1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[2]/SKU'), 'UPS')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/ProviderType'), '70')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/SourceSystem'), 'Oscar')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/TestTransaction'), 'true')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/TransactionID'), '0')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/TransactionType'), '01')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/finalize'), 'false')

        resp = self._get_cch_response_shipping_only_multiple_skus()
        get_transport.return_value = self._build_transport_with_reply(resp, test_request=test_request)

        self.assertFalse(shipping_charge.is_tax_known)
        self.assertEqual(shipping_charge.excl_tax, D('120.00'))

        CCHTaxCalculator().apply_taxes(to_address, shipping_charge=shipping_charge)

        self.assertTrue(shipping_charge.is_tax_known)
        self.assertEqual(shipping_charge.excl_tax, D('120.00'))
        self.assertEqual(shipping_charge.incl_tax, D('124.80'))

        self.assertEqual(len(shipping_charge.components[0].taxation_details), 1)
        self.assertEqual(shipping_charge.components[0].taxation_details[0].authority_name, 'NEW YORK, STATE OF')
        self.assertEqual(shipping_charge.components[0].taxation_details[0].tax_name, 'STATE SALES TAX-GENERAL MERCHANDISE')
        self.assertEqual(shipping_charge.components[0].taxation_details[0].tax_applied, D('4.00'))
        self.assertEqual(shipping_charge.components[0].taxation_details[0].fee_applied, D('0.00'))

        self.assertEqual(len(shipping_charge.components[1].taxation_details), 1)
        self.assertEqual(shipping_charge.components[1].taxation_details[0].authority_name, 'NEW YORK, STATE OF')
        self.assertEqual(shipping_charge.components[1].taxation_details[0].tax_name, 'STATE SALES TAX-GENERAL MERCHANDISE')
        self.assertEqual(shipping_charge.components[1].taxation_details[0].tax_applied, D('0.80'))
        self.assertEqual(shipping_charge.components[1].taxation_details[0].fee_applied, D('0.00'))


    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @mock.patch('soap.http.requests')
    def test_apply_taxes_read_timeout(self, soap_requests):
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        shipping_charge = self.get_shipping_charge()

        # Make requests throw a ReadTimeout
        def raise_error(*args, **kwargs):
            raise requests.exceptions.ReadTimeout()
        soap_requests.post = mock.MagicMock(side_effect=raise_error)

        self.assertFalse(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))
        resp = CCHTaxCalculator().apply_taxes(to_address, basket, shipping_charge)
        self.assertIsNone(resp)
        self.assertTrue(basket.is_tax_known)
        self.assertTrue(shipping_charge.is_tax_known)
        self.assertEqual(shipping_charge.excl_tax, D('14.99'))


    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @mock.patch('soap.http.requests')
    def test_apply_taxes_read_timeout_retried(self, soap_requests):
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        shipping_charge = self.get_shipping_charge()
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
        soap_requests.post = mock.MagicMock(side_effect=raise_error)

        self.assertFalse(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))

        CCHTaxCalculator().apply_taxes(to_address, basket, shipping_charge)

        self.assertEqual(soap_requests.post.call_count, 2)

        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))
        self.assertEqual(basket.total_incl_tax, D('10.89'))
        self.assertEqual(basket.total_tax, D('0.89'))

        self.assertTrue(shipping_charge.is_tax_known)
        self.assertEqual(shipping_charge.excl_tax, D('14.99'))
        self.assertEqual(shipping_charge.incl_tax, D('16.3203625'))
        self.assertEqual(len(shipping_charge.components[0].taxation_details), 3)
        self.assertEqual(shipping_charge.components[0].taxation_details[0].authority_name, 'NEW YORK, STATE OF')
        self.assertEqual(shipping_charge.components[0].taxation_details[0].tax_name, 'STATE SALES TAX-GENERAL MERCHANDISE')
        self.assertEqual(shipping_charge.components[0].taxation_details[0].tax_applied, D('0.5996'))
        self.assertEqual(shipping_charge.components[0].taxation_details[0].fee_applied, D('0.00'))


    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @mock.patch('soap.http.requests')
    def test_apply_taxes_read_timeout_circuit_breaker(self, soap_requests):
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        shipping_charge = self.get_shipping_charge()

        # Make requests throw a ReadTimeout
        def raise_error(*args, **kwargs):
            raise requests.exceptions.ReadTimeout()
        soap_requests.post = mock.MagicMock(side_effect=raise_error)

        self.assertFalse(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))

        circuit_breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=60)
        calc = CCHTaxCalculator(breaker=circuit_breaker)
        calc.max_retries = 0  # Disable internal retries to make the math in this test easier

        self.assertEqual(soap_requests.post.call_count, 0)

        # First call calls web-service
        resp = calc.apply_taxes(to_address, basket, shipping_charge)
        self.assertIsNone(resp)
        self.assertEqual(soap_requests.post.call_count, 1)

        # Second call calls web-service
        resp = calc.apply_taxes(to_address, basket, shipping_charge)
        self.assertIsNone(resp)
        self.assertEqual(soap_requests.post.call_count, 2)

        # Third call calls web-service
        resp = calc.apply_taxes(to_address, basket, shipping_charge)
        self.assertIsNone(resp)
        self.assertEqual(soap_requests.post.call_count, 3)

        # Forth call doesn't even try calling web-service (since the circuit is now open)
        resp = calc.apply_taxes(to_address, basket, shipping_charge)
        self.assertIsNone(resp)
        self.assertEqual(soap_requests.post.call_count, 3, "Counter doesn't get incremented because circuit breaker prevents CCH from ever getting called.")


    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @mock.patch('soap.get_transport')
    def test_apply_taxes_after_discount(self, get_transport):
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        shipping_charge = self.get_shipping_charge()

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
            self.assertNodeCount(request.message, p('Body/CalculateRequest/order/LineItems/LineItem'), 2)
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/AvgUnitPrice'), '5.00000')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/ID'), str(basket.all_lines()[0].id))
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/City'), 'Anchorage')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/CountryCode'), 'US')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/Line1'), '221 Baker st')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/Line2'), 'B')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/PostalCode'), '99501')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/StateOrProvince'), 'AK')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/City'), 'Brooklyn')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/CountryCode'), 'US')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/Line1'), '123 Evergreen Terrace')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/Line2'), 'Apt #1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/PostalCode'), '11201')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/StateOrProvince'), 'NY')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/Quantity'), '1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/SKU'), 'ABC123')
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

        CCHTaxCalculator().apply_taxes(to_address, basket, shipping_charge)

        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('5.00'))
        # self.assertEqual(basket.total_incl_tax, D('5.89'))
        # self.assertEqual(basket.total_tax, D('0.89'))
        self.assertEqual(basket.total_incl_tax, D('5.45'))
        self.assertEqual(basket.total_tax, D('0.45'))

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

        self.assertTrue(shipping_charge.is_tax_known)
        self.assertEqual(shipping_charge.excl_tax, D('14.99'))
        self.assertEqual(shipping_charge.incl_tax, D('16.3203625'))
        self.assertEqual(len(shipping_charge.components[0].taxation_details), 3)
        self.assertEqual(shipping_charge.components[0].taxation_details[0].authority_name, 'NEW YORK, STATE OF')
        self.assertEqual(shipping_charge.components[0].taxation_details[0].tax_name, 'STATE SALES TAX-GENERAL MERCHANDISE')
        self.assertEqual(shipping_charge.components[0].taxation_details[0].tax_applied, D('0.5996'))
        self.assertEqual(shipping_charge.components[0].taxation_details[0].fee_applied, D('0.00'))


    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @mock.patch('soap.get_transport')
    def test_custom_quantity(self, get_transport):
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        shipping_charge = self.get_shipping_charge()

        # Set a custom cch_quantity property
        for basket_line in basket.all_lines():
            basket_line.cch_quantity = 3

        def test_request(request):
            self.assertNodeCount(request.message, p('Body/CalculateRequest/order/LineItems/LineItem'), 2)
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/AvgUnitPrice'), '3.33333')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/ID'), str(basket_line.id))
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/Quantity'), '3')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/SKU'), 'ABC123')

        resp = self._get_cch_response_normal(basket_line.id)
        get_transport.return_value = self._build_transport_with_reply(resp, test_request=test_request)

        self.assertFalse(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))

        CCHTaxCalculator().apply_taxes(to_address, basket, shipping_charge)

        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))
        self.assertEqual(basket.total_incl_tax, D('10.89'))
        self.assertEqual(basket.total_tax, D('0.89'))

        self.assertTrue(shipping_charge.is_tax_known)
        self.assertEqual(shipping_charge.excl_tax, D('14.99'))
        self.assertEqual(shipping_charge.incl_tax, D('16.3203625'))
        self.assertEqual(len(shipping_charge.components[0].taxation_details), 3)
        self.assertEqual(shipping_charge.components[0].taxation_details[0].authority_name, 'NEW YORK, STATE OF')
        self.assertEqual(shipping_charge.components[0].taxation_details[0].tax_name, 'STATE SALES TAX-GENERAL MERCHANDISE')
        self.assertEqual(shipping_charge.components[0].taxation_details[0].tax_applied, D('0.5996'))
        self.assertEqual(shipping_charge.components[0].taxation_details[0].fee_applied, D('0.00'))


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
            price=D('10.00'))
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
        shipping_charge = self.get_shipping_charge()

        def test_request(request):
            self.assertNodeText(request.message, p('Body/CalculateRequest/EntityID'), 'TESTSANDBOX')
            self.assertNodeText(request.message, p('Body/CalculateRequest/DivisionID'), '42')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/CustomerType'), '08')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/InvoiceDate'), '2016-04-13T12:14:44.018599-04:00')
            self.assertNodeCount(request.message, p('Body/CalculateRequest/order/LineItems/LineItem'), 2)
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/AvgUnitPrice'), '10.00000')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/ID'), str(basket.all_lines()[0].id))
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/City'), 'Anchorage')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/CountryCode'), 'US')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/Line1'), '221 Baker st')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/Line2'), 'B')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/PostalCode'), '99501')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/StateOrProvince'), 'AK')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/City'), 'Brooklyn')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/CountryCode'), 'US')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/Line1'), '123 Evergreen Terrace')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/Line2'), 'Apt #1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/PostalCode'), '11201')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/StateOrProvince'), 'NY')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/Quantity'), '1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/SKU'), 'XYZ456')
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

        CCHTaxCalculator().apply_taxes(to_address, basket, shipping_charge)

        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))
        self.assertEqual(basket.total_incl_tax, D('10.89'))
        self.assertEqual(basket.total_tax, D('0.89'))

        purchase_info = basket.all_lines()[0].purchase_info
        self.assertEqual(purchase_info.price.excl_tax, D('10.00'))
        self.assertEqual(purchase_info.price.incl_tax, D('10.89'))
        self.assertEqual(purchase_info.price.tax, D('0.89'))

        self.assertTrue(shipping_charge.is_tax_known)
        self.assertEqual(shipping_charge.excl_tax, D('14.99'))
        self.assertEqual(shipping_charge.incl_tax, D('16.3203625'))
        self.assertEqual(len(shipping_charge.components[0].taxation_details), 3)
        self.assertEqual(shipping_charge.components[0].taxation_details[0].authority_name, 'NEW YORK, STATE OF')
        self.assertEqual(shipping_charge.components[0].taxation_details[0].tax_name, 'STATE SALES TAX-GENERAL MERCHANDISE')
        self.assertEqual(shipping_charge.components[0].taxation_details[0].tax_applied, D('0.5996'))
        self.assertEqual(shipping_charge.components[0].taxation_details[0].fee_applied, D('0.00'))


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
            price=D('10.00'))
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
        shipping_charge = self.get_shipping_charge()

        def test_request(request):
            self.assertNodeText(request.message, p('Body/CalculateRequest/EntityID'), 'TESTSANDBOX')
            self.assertNodeText(request.message, p('Body/CalculateRequest/DivisionID'), '42')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/CustomerType'), '08')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/InvoiceDate'), '2016-04-13T12:14:44.018599-04:00')
            self.assertNodeCount(request.message, p('Body/CalculateRequest/order/LineItems/LineItem'), 2)
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/AvgUnitPrice'), '10.00000')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/ID'), str(basket.all_lines()[0].id))
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/City'), 'Anchorage')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/CountryCode'), 'US')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/Line1'), '221 Baker st')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/Line2'), 'B')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/PostalCode'), '99501')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/StateOrProvince'), 'AK')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/City'), 'Brooklyn')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/CountryCode'), 'US')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/Line1'), '123 Evergreen Terrace')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/Line2'), 'Apt #1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/PostalCode'), '11201')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/StateOrProvince'), 'NY')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/Quantity'), '1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/SKU'), 'ABC123')
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

        CCHTaxCalculator().apply_taxes(to_address, basket, shipping_charge)

        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))
        self.assertEqual(basket.total_incl_tax, D('10.89'))
        self.assertEqual(basket.total_tax, D('0.89'))

        purchase_info = basket.all_lines()[0].purchase_info
        self.assertEqual(purchase_info.price.excl_tax, D('10.00'))
        self.assertEqual(purchase_info.price.incl_tax, D('10.89'))
        self.assertEqual(purchase_info.price.tax, D('0.89'))

        self.assertTrue(shipping_charge.is_tax_known)
        self.assertEqual(shipping_charge.excl_tax, D('14.99'))
        self.assertEqual(shipping_charge.incl_tax, D('16.3203625'))
        self.assertEqual(len(shipping_charge.components[0].taxation_details), 3)
        self.assertEqual(shipping_charge.components[0].taxation_details[0].authority_name, 'NEW YORK, STATE OF')
        self.assertEqual(shipping_charge.components[0].taxation_details[0].tax_name, 'STATE SALES TAX-GENERAL MERCHANDISE')
        self.assertEqual(shipping_charge.components[0].taxation_details[0].tax_applied, D('0.5996'))
        self.assertEqual(shipping_charge.components[0].taxation_details[0].fee_applied, D('0.00'))


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
            price=D('10.00'))
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
        shipping_charge = self.get_shipping_charge()

        def test_request(request):
            self.assertNodeText(request.message, p('Body/CalculateRequest/EntityID'), 'TESTSANDBOX')
            self.assertNodeText(request.message, p('Body/CalculateRequest/DivisionID'), '42')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/CustomerType'), '08')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/InvoiceDate'), '2016-04-13T12:14:44.018599-04:00')
            self.assertNodeCount(request.message, p('Body/CalculateRequest/order/LineItems/LineItem'), 2)
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/AvgUnitPrice'), '10.00000')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/ID'), str(basket.all_lines()[0].id))
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/City'), 'Anchorage')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/CountryCode'), 'US')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/Line1'), '221 Baker st')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/Line2'), 'B')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/PostalCode'), '99501')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/StateOrProvince'), 'AK')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/City'), 'Brooklyn')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/CountryCode'), 'US')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/Line1'), '123 Evergreen Terrace')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/Line2'), 'Apt #1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/PostalCode'), '11201')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/StateOrProvince'), 'NY')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/Quantity'), '1')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/SKU'), 'ABC123')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/ProductInfo/ProductGroup'), 'MyGroup')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/ProductInfo/ProductItem'), 'MyItem')
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

        CCHTaxCalculator().apply_taxes(to_address, basket, shipping_charge)

        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))
        self.assertEqual(basket.total_incl_tax, D('10.89'))
        self.assertEqual(basket.total_tax, D('0.89'))

        purchase_info = basket.all_lines()[0].purchase_info
        self.assertEqual(purchase_info.price.excl_tax, D('10.00'))
        self.assertEqual(purchase_info.price.incl_tax, D('10.89'))
        self.assertEqual(purchase_info.price.tax, D('0.89'))

        self.assertTrue(shipping_charge.is_tax_known)
        self.assertEqual(shipping_charge.excl_tax, D('14.99'))
        self.assertEqual(shipping_charge.incl_tax, D('16.3203625'))
        self.assertEqual(len(shipping_charge.components[0].taxation_details), 3)
        self.assertEqual(shipping_charge.components[0].taxation_details[0].authority_name, 'NEW YORK, STATE OF')
        self.assertEqual(shipping_charge.components[0].taxation_details[0].tax_name, 'STATE SALES TAX-GENERAL MERCHANDISE')
        self.assertEqual(shipping_charge.components[0].taxation_details[0].tax_applied, D('0.5996'))
        self.assertEqual(shipping_charge.components[0].taxation_details[0].fee_applied, D('0.00'))


    @mock.patch('soap.get_transport')
    def test_truncate_postal_code(self, get_transport):
        basket = self.prepare_basket()
        to_address = self.get_to_address()

        def test_request(request):
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/PostalCode'), '99501')
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/PostalCode'), '11201')
        resp = self._get_cch_response_normal( basket.all_lines()[0].id )
        get_transport.return_value = self._build_transport_with_reply(resp, test_request=test_request)

        self.assertFalse(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))

        from_address = basket.all_lines()[0].stockrecord.partner.primary_address
        from_address.postcode = '99501-1234'
        from_address.save()

        to_address.postcode = '11201-9876'
        to_address.save()

        shipping_charge = self.get_shipping_charge()

        CCHTaxCalculator().apply_taxes(to_address, basket, shipping_charge)

        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))
        self.assertEqual(basket.total_incl_tax, D('10.89'))

        self.assertTrue(shipping_charge.is_tax_known)
        self.assertEqual(shipping_charge.excl_tax, D('14.99'))
        self.assertEqual(shipping_charge.incl_tax, D('16.3203625'))
        self.assertEqual(len(shipping_charge.components[0].taxation_details), 3)
        self.assertEqual(shipping_charge.components[0].taxation_details[0].authority_name, 'NEW YORK, STATE OF')
        self.assertEqual(shipping_charge.components[0].taxation_details[0].tax_name, 'STATE SALES TAX-GENERAL MERCHANDISE')
        self.assertEqual(shipping_charge.components[0].taxation_details[0].tax_applied, D('0.5996'))
        self.assertEqual(shipping_charge.components[0].taxation_details[0].fee_applied, D('0.00'))


    @mock.patch('soap.get_transport')
    def test_apply_taxes_repeatedly(self, get_transport):
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        shipping_charge = self.get_shipping_charge()
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

            self.assertTrue(shipping_charge.is_tax_known)
            self.assertEqual(shipping_charge.excl_tax, D('14.99'))
            self.assertEqual(shipping_charge.incl_tax, D('16.3203625'))
            self.assertEqual(len(shipping_charge.components[0].taxation_details), 3)
            self.assertEqual(shipping_charge.components[0].taxation_details[0].authority_name, 'NEW YORK, STATE OF')
            self.assertEqual(shipping_charge.components[0].taxation_details[0].tax_name, 'STATE SALES TAX-GENERAL MERCHANDISE')
            self.assertEqual(shipping_charge.components[0].taxation_details[0].tax_applied, D('0.5996'))
            self.assertEqual(shipping_charge.components[0].taxation_details[0].fee_applied, D('0.00'))

        self.assertFalse(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))

        CCHTaxCalculator().apply_taxes(to_address, basket, shipping_charge)
        assert_taxes_are_correct()

        CCHTaxCalculator().apply_taxes(to_address, basket, shipping_charge)
        assert_taxes_are_correct()

        CCHTaxCalculator().apply_taxes(to_address, basket, shipping_charge)
        assert_taxes_are_correct()


    @mock.patch('soap.get_transport')
    def test_apply_taxes_tax_free(self, get_transport):
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        shipping_charge = self.get_shipping_charge()

        resp = self._get_cch_response_empty()
        get_transport.return_value = self._build_transport_with_reply(resp)

        self.assertFalse(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))

        CCHTaxCalculator().apply_taxes(to_address, basket, shipping_charge)

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

        self.assertTrue(shipping_charge.is_tax_known)
        self.assertEqual(shipping_charge.excl_tax, D('14.99'))
        self.assertEqual(shipping_charge.incl_tax, D('14.99'))
        self.assertEqual(len(shipping_charge.components[0].taxation_details), 0)


    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @mock.patch('soap.get_transport')
    def test_apply_taxes_zero_qty_line(self, get_transport):
        basket = self.prepare_basket(lines=2)
        to_address = self.get_to_address()
        shipping_charge = self.get_shipping_charge()

        basket.add_product(basket.all_lines()[0].product, -1)

        def test_request(request):
            self.assertNodeCount(request.message, p('Body/CalculateRequest/order/LineItems/LineItem'), 2)
            self.assertNodeText(request.message, p('Body/CalculateRequest/order/LineItems/LineItem[1]/AvgUnitPrice'), '10.00000')

        resp = self._get_cch_response_normal(basket.all_lines()[1].id)
        get_transport.return_value = self._build_transport_with_reply(resp, test_request=test_request)

        self.assertFalse(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))

        CCHTaxCalculator().apply_taxes(to_address, basket, shipping_charge)

        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))
        self.assertEqual(basket.total_incl_tax, D('10.89'))
        self.assertEqual(basket.total_tax, D('0.89'))

        self.assertEqual(len(basket.all_lines()), 2)

        self.assertTrue(shipping_charge.is_tax_known)
        self.assertEqual(shipping_charge.excl_tax, D('14.99'))
        self.assertEqual(shipping_charge.incl_tax, D('16.3203625'))
        self.assertEqual(len(shipping_charge.components[0].taxation_details), 3)
        self.assertEqual(shipping_charge.components[0].taxation_details[0].authority_name, 'NEW YORK, STATE OF')
        self.assertEqual(shipping_charge.components[0].taxation_details[0].tax_name, 'STATE SALES TAX-GENERAL MERCHANDISE')
        self.assertEqual(shipping_charge.components[0].taxation_details[0].tax_applied, D('0.5996'))
        self.assertEqual(shipping_charge.components[0].taxation_details[0].fee_applied, D('0.00'))


    @mock.patch('soap.get_transport')
    def test_apply_taxes_cch_db_error_passes_silently(self, get_transport):
        basket = self.prepare_basket()
        to_address = self.get_to_address()
        shipping_charge = self.get_shipping_charge()

        resp = self._get_cch_response_db_connection_error()
        get_transport.return_value = self._build_transport_with_reply(resp)

        self.assertFalse(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))

        resp = CCHTaxCalculator().apply_taxes(to_address, basket, shipping_charge)

        self.assertIsNone(resp)
        self.assertTrue(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D('10.00'))

        self.assertTrue(shipping_charge.is_tax_known)
        self.assertEqual(shipping_charge.excl_tax, D('14.99'))
