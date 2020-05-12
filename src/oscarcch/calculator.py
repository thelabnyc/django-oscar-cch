from datetime import datetime
from decimal import Decimal
from . import exceptions, settings
import logging
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


    def apply_taxes(self, shipping_address, basket=None, shipping_charge=None):
        """
        Apply taxes to a Basket instance using the given shipping address.

        Pass return value of this method to :func:`OrderTaxation.save_details <oscarcch.models.OrderTaxation.save_details>`
        to persist the taxation details, CCH transaction ID, etc in the database.

        :param shipping_address: :class:`ShippingAddress <oscar.apps.order.models.ShippingAddress>` instance
        :param basket: :class:`Basket <oscar.apps.basket.models.Basket>` instance
        :param shipping_charge: :class:`ShippingCharge <oscarcch.prices.ShippingCharge>` instance
        :return: SOAP Response.
        """
        response = self._get_response(shipping_address, basket, shipping_charge)

        # Check the response for errors
        respOK = self._check_response_messages(response)
        if not respOK:
            response = None

        # Build map of line IDs to line tax details
        cch_line_map = {}
        if response and response.LineItemTaxes:
            cch_line_map = { item.ID: item for item in response.LineItemTaxes.LineItemTax }

        # Apply taxes to line items
        if basket is not None:
            for line in basket.all_lines():
                line_id = str(line.id)
                taxes = cch_line_map.get(line_id)
                self._apply_taxes_to_price(taxes, line.purchase_info.price, line.quantity)

        # Apply taxes to shipping charge
        if shipping_charge is not None:
            for shipping_charge_component in shipping_charge.components:
                shipping_taxes = cch_line_map.get(shipping_charge_component.cch_line_id)
                self._apply_taxes_to_price(shipping_taxes, shipping_charge_component, 1)

        # Return CCH response
        return response


    def _apply_taxes_to_price(self, taxes, price, quantity):
        # Taxes come in two forms: quantity and percentage based
        # We need to handle both of those here. The tricky part is that CCH returns data
        # for an entire line item (inclusive quantity), but Oscar needs the tax info for
        # each unit in the line (exclusive quantity). So, we use the details provided to
        # derive the per-unit taxes before applying them.
        price.clear_taxes()
        if taxes:
            for tax in taxes.TaxDetails.TaxDetail:
                unit_fee = Decimal(str(tax.FeeApplied)) / quantity
                unit_tax = Decimal(str(tax.TaxApplied)) / quantity
                price.add_tax(
                    authority_name=tax.AuthorityName,
                    tax_name=tax.TaxName,
                    tax_applied=unit_tax,
                    fee_applied=unit_fee)
            # Check our work and make sure the total we arrived at matches the total CCH gave us
            total_line_tax = (price.tax * quantity).quantize(self.precision)
            total_applied_tax = Decimal(taxes.TotalTaxApplied).quantize(self.precision)
            if total_applied_tax != total_line_tax:
                raise RuntimeError((
                    "Taxation miscalculation occurred! "
                    "Details sum to %s, which doesn't match given sum of %s"
                ) % (total_line_tax, taxes.TotalTaxApplied))
        else:
            price.tax = Decimal('0.00')



    def _get_response(self, shipping_address, basket, shipping_charge):
        """Fetch CCH tax data for the given basket and shipping address"""
        response = None
        retry_count = 0
        while response is None and retry_count <= self.max_retries:
            response = self._get_response_inner(shipping_address, basket, shipping_charge,
                retry_count=retry_count)
            retry_count += 1
        return response


    def _get_response_inner(self, shipping_address, basket, shipping_charge, retry_count):
        response = None

        def _call_service():
            order = self._build_order(shipping_address, basket, shipping_charge)
            if order is None:
                return None
            response = self.client.service.CalculateRequest(self.entity_id, self.divsion_id, order)
            return response

        try:
            if self.breaker is not None:
                response = self.breaker.call(_call_service)
            else:
                response = _call_service()
        except Exception as e:
            logger.exception(e)
        return response


    def _check_response_messages(self, response):
        """Raise an exception if response messages contains any reported errors."""
        if response is None:
            return False
        if response.Messages:
            for message in response.Messages.Message:
                if message.Code > 0:
                    exc = exceptions.build(message.Severity, message.Code, message.Info)
                    logger.exception(exc)
                    return False
        return True


    @property
    def client(self):
        """Lazy constructor for SOAP client"""
        return soap.get_client(self.wsdl, 'CCH')


    def _build_order(self, shipping_address, basket, shipping_charge):
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

        # Add CCH lines for each basket line
        if basket is not None:
            for line in basket.all_lines():
                qty = getattr(line, 'cch_quantity', line.quantity)
                if qty <= 0:
                    continue
                # Line Info
                item = self.client.factory.create('ns11:LineItem')
                item.ID = line.id
                item.AvgUnitPrice = Decimal(line.line_price_excl_tax_incl_discounts / qty).quantize(Decimal('0.00001'))
                item.Quantity = qty
                item.ExemptionCode = None
                item.SKU = self._get_product_data('sku', line)
                # Product Info
                item.ProductInfo = self.client.factory.create('ns21:ProductInfo')
                item.ProductInfo.ProductGroup = self._get_product_data('group', line)
                item.ProductInfo.ProductItem = self._get_product_data('item', line)
                # Ship From/To Addresses
                item.NexusInfo = self.client.factory.create('ns14:NexusInfo')
                warehouse = line.stockrecord.partner.primary_address
                if warehouse:
                    item.NexusInfo.ShipFromAddress = self._build_address(warehouse)
                item.NexusInfo.ShipToAddress = self._build_address(shipping_address)
                # Add line to order
                order.LineItems.LineItem.append(item)

        # Add CCH lines for shipping charges
        if shipping_charge is not None and settings.CCH_SHIPPING_TAXES_ENABLED:
            for shipping_charge_component in shipping_charge.components:
                shipping_line = self.client.factory.create('ns11:LineItem')
                shipping_line.ID = shipping_charge_component.cch_line_id
                shipping_line.AvgUnitPrice = shipping_charge_component.excl_tax.quantize(Decimal('0.00001'))
                shipping_line.Quantity = 1
                shipping_line.ExemptionCode = None
                shipping_line.SKU = shipping_charge_component.cch_sku
                shipping_line.NexusInfo = self.client.factory.create('ns14:NexusInfo')
                shipping_line.NexusInfo.ShipToAddress = self._build_address(shipping_address)
                # Add shipping line to order
                order.LineItems.LineItem.append(shipping_line)

        # Must include at least 1 line item
        if len(order.LineItems.LineItem) <= 0:
            return None

        # Return order
        return order


    def _build_address(self, oscar_address):
        addr = self.client.factory.create('ns0:Address')
        addr.Line1 = oscar_address.line1
        addr.Line2 = oscar_address.line2
        addr.City = oscar_address.city
        addr.StateOrProvince = oscar_address.state
        postcode, plus4 = self.format_postcode(oscar_address.postcode)
        addr.PostalCode = postcode
        addr.Plus4 = plus4
        addr.CountryCode = oscar_address.country.code
        return addr


    def _get_product_data(self, key, line):
        key = 'cch_product_%s' % key
        sku = getattr(settings, key.upper())
        sku = getattr(line.product.attr, key.lower(), sku)
        return sku


    def format_postcode(self, raw_postcode):
        if not raw_postcode:
            return '', ''
        postcode, plus4 = raw_postcode[:POSTCODE_LEN], None
        # Set Plus4 if PostalCode provided as 9 digits separated by hyphen
        if len(raw_postcode) == POSTCODE_LEN + PLUS4_LEN + 1:
            plus4 = raw_postcode[POSTCODE_LEN + 1:]
        return postcode, plus4
