from datetime import datetime
from decimal import Decimal
from django.core.cache import caches
from django_statsd.clients import statsd
import logging

from . import exceptions, settings
from .cache import get_basket_uat

import suds.client
try:
    import soap
except ImportError:
    soap = None

try:
    from raven.contrib.django.raven_compat.models import client as raven_client
except ImportError:
    raven_client = None



logger = logging.getLogger(__name__)
cache = caches[settings.CCH_CACHE_BACKEND]


class CCHTaxCalculator(object):
    precision = settings.CCH_PRECISION
    wsdl = settings.CCH_WSDL
    entity_id = settings.CCH_ENTITY
    divsion_id = settings.CCH_DIVISION


    def estimate_taxes(self, basket, shipping_address):
        cache_key = '%s_tax_%s_%s_%s_%s' % (__name__, basket.id, get_basket_uat(basket), shipping_address.state, shipping_address.postcode)
        cached_basket = cache.get(cache_key)
        statsd.incr('cch.estimate')
        if cached_basket is not None:
            return cached_basket
        statsd.incr('cch.estimate-cache-miss')
        self.apply_taxes(basket, shipping_address)
        cache.set(cache_key, basket, settings.CCH_ESTIMATE_CACHE_SECONDS)
        return basket


    def apply_taxes(self, basket, shipping_address, ignore_cch_fail=False):
        response = self._get_response(basket, shipping_address, ignore_cch_fail)
        if not ignore_cch_fail:
            self._check_response_messages(response)

        # Apply taxes to line items
        for line in basket.all_lines():
            line_id = str(line.id)

            taxes = None
            if response and response.LineItemTaxes:
                taxes = next(filter(lambda item: item.ID == line_id, response.LineItemTaxes.LineItemTax))

            # Taxes come in two forms: quantity and percentage based
            # We need to handle both of those here. The tricky part is that CCH returns data
            # for an entire line item (inclusive quantity), but Oscar needs the tax info for
            # each unit in the line (exclusive quantity). So, we use the details provided to
            # derive the per-unit taxes before applying them.
            line.purchase_info.price.clear_taxes()
            if taxes:
                for tax in taxes.TaxDetails.TaxDetail:
                    unit_fee = Decimal(str(tax.FeeApplied)) / line.quantity
                    unit_tax = Decimal(str(tax.TaxApplied)) / line.quantity
                    line.purchase_info.price.add_tax(
                        authority_name=tax.AuthorityName,
                        tax_name=tax.TaxName,
                        tax_applied=unit_tax,
                        fee_applied=unit_fee)
                # Check our work and make sure the total we arrived at matches the total CCH gave us
                total_line_tax = (line.purchase_info.price.tax * line.quantity).quantize(self.precision)
                total_applied_tax = Decimal(taxes.TotalTaxApplied).quantize(self.precision)
                if total_applied_tax != total_line_tax:
                    statsd.incr('cch.miscalculation')
                    raise RuntimeError("Taxation miscalculation occurred! Details sum to %s, which doesn't match given sum of %s" % (total_line_tax, taxes.TotalTaxApplied))
            else:
                line.purchase_info.price.tax = Decimal('0.00')

        return response


    def _get_response(self, basket, shipping_address, ignore_cch_fail=False):
        """Fetch CCH tax data for the given basket and shipping address"""
        response = None
        try:
            order = self._build_order(basket, shipping_address)
            response = self.client.service.CalculateRequest(self.entity_id, self.divsion_id, order)
        except Exception as e: # It's unclear what exceptions suds will actually throw. There is no suds base exception
            statsd.incr('cch.apply-failure')
            if raven_client is not None:
                raven_client.captureException()
            if not ignore_cch_fail:
                raise e
        return response


    def _check_response_messages(self, response):
        """Raise an exception if response messages contains any reported errors."""
        if response and response.Messages:
            for message in response.Messages.Message:
                if message.Code > 0:
                    raise exceptions.build(message.Severity, message.Code, message.Info)


    @property
    def client(self):
        """Lazy constructor for SOAP client"""
        if soap is None:
            return suds.client.Client(self.wsdl)
        return soap.get_client(self.wsdl, 'CCH')


    def _build_order(self, basket, shipping_address):
        """Convert an Oscar Basket and ShippingAddresss into a CCH Order object"""
        order = self.client.factory.create('ns15:Order')

        order.InvoiceDate = datetime.now(settings.CCH_TIME_ZONE)
        order.SourceSystem = settings.CCH_SOURCE_SYSTEM
        order.TestTransaction = settings.CCH_TEST_TRANSACTIONS
        order.TransactionType = settings.CCH_TRANSACTION_TYPE
        order.CustomerType = settings.CCH_CUSTOMER_TYPE
        order.ProviderType = settings.CCH_PROVIDER_TYPE
        order.TransactionID = 0
        order.finalize = settings.CCH_FINALIZE_TRANSACTION

        for line in basket.all_lines():
            item = self.client.factory.create('ns11:LineItem')
            item.ID = line.id
            item.AvgUnitPrice = line.price_excl_tax
            item.Quantity = line.quantity
            item.ExemptionCode = None
            item.SKU = self._get_product_data('sku', line)
            item.ProductInfo = self.client.factory.create('ns21:ProductInfo')
            item.ProductInfo.ProductGroup = self._get_product_data('group', line)
            item.ProductInfo.ProductItem = self._get_product_data('item', line)

            item.NexusInfo = self.client.factory.create('ns14:NexusInfo')

            item.NexusInfo.ShipFromAddress = self.client.factory.create('ns0:Address')
            warehouse = line.stockrecord.partner.primary_address
            if warehouse:
                item.NexusInfo.ShipFromAddress.Line1 = warehouse.line1
                item.NexusInfo.ShipFromAddress.Line2 = warehouse.line2
                item.NexusInfo.ShipFromAddress.City = warehouse.city
                item.NexusInfo.ShipFromAddress.StateOrProvince = warehouse.state
                item.NexusInfo.ShipFromAddress.PostalCode = warehouse.postcode[:settings.CCH_POSTALCODE_LENGTH]
                item.NexusInfo.ShipFromAddress.CountryCode = warehouse.country.code
            item.NexusInfo.ShipToAddress = self.client.factory.create('ns0:Address')
            item.NexusInfo.ShipToAddress.Line1 = shipping_address.line1
            item.NexusInfo.ShipToAddress.Line2 = shipping_address.line2
            item.NexusInfo.ShipToAddress.City = shipping_address.city
            item.NexusInfo.ShipToAddress.StateOrProvince = shipping_address.state
            item.NexusInfo.ShipToAddress.PostalCode = shipping_address.postcode[:settings.CCH_POSTALCODE_LENGTH]
            item.NexusInfo.ShipToAddress.CountryCode = shipping_address.country.code

            order.LineItems.LineItem.append(item)

        return order


    def _get_product_data(self, key, line):
        key = 'cch_product_%s' % key
        sku = getattr(settings, key.upper())
        sku = getattr(line.product.attr, key.lower(), sku)
        return sku
