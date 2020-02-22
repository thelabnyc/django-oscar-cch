from datetime import datetime
from decimal import Decimal
from . import exceptions, settings
import logging
import requests
import soap

logger = logging.getLogger(__name__)

POSTCODE_LEN = 5
PLUS4_LEN = 4


class CCHTaxCalculator(object):
    """
    Simple interface between Python and the CCH Sales Tax Office SOAP API.
    """
    precision = settings.CCH_PRECISION
    wsdl = settings.CCH_WSDL
    entity_id = settings.CCH_ENTITY
    divsion_id = settings.CCH_DIVISION
    max_retries = settings.CCH_MAX_RETRIES


    def __init__(self, breaker=None):
        """
        Construct a CCHTaxCalculator instance

        You may optionally supply a ``pybreaker.CircuitBreaker`` instance. If you do so, it will be used to
        implement the CircuitBreaker pattern around the SOAP calls to the CCH web service.

        :param breaker: Optional :class:`CircuitBreaker <pybreaker.CircuitBreaker>` instance
        """
        self.breaker = breaker


    def estimate_taxes(self, basket, shipping_address):
        """
        DEPRECATED. Use :func:`CCHTaxCalculator.apply_taxes <oscarcch.calculator.CCHTaxCalculator.apply_taxes>` instead.
        """
        self.apply_taxes(basket, shipping_address)
        return basket


    def apply_taxes(self, basket, shipping_address, ignore_cch_fail=False):
        """
        Apply taxes to a Basket instance using the given shipping address.

        Pass return value of this method to :func:`OrderTaxation.save_details <oscarcch.models.OrderTaxation.save_details>`
        to persist the taxation details, CCH transaction ID, etc in the database.

        :param basket: :class:`Basket <oscar.apps.basket.models.Basket>` instance
        :param shipping_address: :class:`ShippingAddress <oscar.apps.order.models.ShippingAddress>` instance
        :param ignore_cch_fail: When `True`, allows CCH to fail silently
        :return: SOAP Response.
        """
        response = self._get_response(basket, shipping_address, ignore_cch_fail)

        # Check the response for errors
        respOK = self._check_response_messages(response, ignore_cch_fail)
        if not respOK:
            return None

        # Apply taxes to line items
        for line in basket.all_lines():
            line_id = str(line.id)

            taxes = None
            if response and response.LineItemTaxes:
                try:
                    taxes = next(filter(lambda item: item.ID == line_id, response.LineItemTaxes.LineItemTax))
                except StopIteration:
                    pass

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
                    raise RuntimeError((
                        "Taxation miscalculation occurred! "
                        "Details sum to %s, which doesn't match given sum of %s"
                    ) % (total_line_tax, taxes.TotalTaxApplied))
            else:
                line.purchase_info.price.tax = Decimal('0.00')

        return response


    def _get_response(self, basket, shipping_address, ignore_cch_fail=False):
        """Fetch CCH tax data for the given basket and shipping address"""
        response = None
        retry_count = 0
        while response is None and retry_count <= self.max_retries:
            response = self._get_response_inner(basket, shipping_address, ignore_cch_fail, retry_count=retry_count)
            retry_count += 1
        return response


    def _get_response_inner(self, basket, shipping_address, ignore_cch_fail, retry_count):
        # Attempt to get a response
        response = None

        def _call_service():
            order = self._build_order(basket, shipping_address)
            response = self.client.service.CalculateRequest(self.entity_id, self.divsion_id, order)
            return response

        try:
            if self.breaker is not None:
                response = self.breaker.call(_call_service)
            else:
                response = _call_service()

        # Timeouts (read or connect) get retried
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if retry_count >= self.max_retries and not ignore_cch_fail:
                raise e

        # Catch any other possible exceptions and, if we're supposed to, ignore them.
        except Exception as e:
            if not ignore_cch_fail:
                raise e

        # Return our (apparently successful) response
        return response


    def _check_response_messages(self, response, ignore_cch_fail):
        """Raise an exception if response messages contains any reported errors."""
        if response and response.Messages:
            for message in response.Messages.Message:
                if message.Code > 0:
                    exc = exceptions.build(message.Severity, message.Code, message.Info)
                    if ignore_cch_fail:
                        logger.exception(exc)
                    else:
                        raise exc
                    return False
        return True


    @property
    def client(self):
        """Lazy constructor for SOAP client"""
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
            qty = getattr(line, 'cch_quantity', line.quantity)
            if qty <= 0:
                continue

            item = self.client.factory.create('ns11:LineItem')
            item.ID = line.id
            item.AvgUnitPrice = Decimal(line.line_price_excl_tax_incl_discounts / qty).quantize(Decimal('0.00001'))
            item.Quantity = qty
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
                postcode, plus4 = self.format_postcode(warehouse.postcode)
                item.NexusInfo.ShipFromAddress.PostalCode = postcode
                item.NexusInfo.ShipFromAddress.Plus4 = plus4
                item.NexusInfo.ShipFromAddress.CountryCode = warehouse.country.code
            item.NexusInfo.ShipToAddress = self.client.factory.create('ns0:Address')
            item.NexusInfo.ShipToAddress.Line1 = shipping_address.line1
            item.NexusInfo.ShipToAddress.Line2 = shipping_address.line2
            item.NexusInfo.ShipToAddress.City = shipping_address.city
            item.NexusInfo.ShipToAddress.StateOrProvince = shipping_address.state
            postcode, plus4 = self.format_postcode(shipping_address.postcode)
            item.NexusInfo.ShipToAddress.PostalCode = postcode
            item.NexusInfo.ShipToAddress.Plus4 = plus4
            item.NexusInfo.ShipToAddress.CountryCode = shipping_address.country.code

            order.LineItems.LineItem.append(item)

        return order


    def _get_product_data(self, key, line):
        key = 'cch_product_%s' % key
        sku = getattr(settings, key.upper())
        sku = getattr(line.product.attr, key.lower(), sku)
        return sku

    def format_postcode(self, raw_postcode):
        postcode, plus4 = raw_postcode[:POSTCODE_LEN], None
        # set Plus4 if PostalCode provided as 9 digits separated by hyphen
        if len(raw_postcode) == POSTCODE_LEN + PLUS4_LEN + 1:
            plus4 = raw_postcode[POSTCODE_LEN + 1:]
        return postcode, plus4
