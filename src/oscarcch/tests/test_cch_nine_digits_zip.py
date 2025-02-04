from decimal import Decimal as D

from freezegun import freeze_time
from oscar.core.loading import get_class, get_model
import requests_mock

from ..calculator import CCHTaxCalculator
from .base import BaseTest, p

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


class CCHTaxCalculatorRealTest(BaseTest):
    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @requests_mock.mock()
    def test_apply_taxes_five_digits_postal_code(self, rmock):
        basket = self.prepare_basket_full_zip()
        to_address = self.get_to_address_ohio_short_zip()
        shipping_charge = self.get_shipping_charge()

        def test_request(request):
            self.assertNodeText(
                request.body, p("Body/CalculateRequest/EntityID"), "TESTSANDBOX"
            )
            self.assertNodeText(
                request.body, p("Body/CalculateRequest/DivisionID"), "42"
            )
            self.assertNodeText(
                request.body, p("Body/CalculateRequest/order/CustomerType"), "08"
            )
            self.assertNodeText(
                request.body,
                p("Body/CalculateRequest/order/InvoiceDate"),
                "2016-04-13T12:14:44.018599-04:00",
            )
            self.assertNodeCount(
                request.body, p("Body/CalculateRequest/order/LineItems/LineItem"), 2
            )
            self.assertNodeText(
                request.body,
                p("Body/CalculateRequest/order/LineItems/LineItem[1]/AvgUnitPrice"),
                "10.00000",
            )
            self.assertNodeText(
                request.body,
                p("Body/CalculateRequest/order/LineItems/LineItem[1]/ID"),
                str(basket.all_lines()[0].id),
            )
            self.assertNodeText(
                request.body,
                p(
                    "Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/City"
                ),
                "Anchorage",
            )
            self.assertNodeText(
                request.body,
                p(
                    "Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/CountryCode"
                ),
                "US",
            )
            self.assertNodeText(
                request.body,
                p(
                    "Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/Line1"
                ),
                "325 F st",
            )
            self.assertNodeText(
                request.body,
                p(
                    "Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/PostalCode"
                ),
                "99501",
            )
            self.assertNodeText(
                request.body,
                p(
                    "Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/Plus4"
                ),
                "2217",
            )
            self.assertNodeText(
                request.body,
                p(
                    "Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/StateOrProvince"
                ),
                "AK",
            )
            self.assertNodeText(
                request.body,
                p(
                    "Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/City"
                ),
                "BRINKHAVEN",
            )
            self.assertNodeText(
                request.body,
                p(
                    "Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/CountryCode"
                ),
                "US",
            )
            self.assertNodeText(
                request.body,
                p(
                    "Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/Line1"
                ),
                "33001 STATE ROUTE 206",
            )
            self.assertNodeText(
                request.body,
                p(
                    "Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/PostalCode"
                ),
                "43006",
            )
            self.assertNodeText(
                request.body,
                p(
                    "Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/StateOrProvince"
                ),
                "OH",
            )
            self.assertNodeText(
                request.body,
                p("Body/CalculateRequest/order/LineItems/LineItem[1]/Quantity"),
                "1",
            )
            self.assertNodeText(
                request.body,
                p("Body/CalculateRequest/order/LineItems/LineItem[1]/SKU"),
                "ABC123",
            )
            self.assertNodeText(
                request.body, p("Body/CalculateRequest/order/ProviderType"), "70"
            )
            self.assertNodeText(
                request.body, p("Body/CalculateRequest/order/SourceSystem"), "Oscar"
            )
            self.assertNodeText(
                request.body,
                p("Body/CalculateRequest/order/TestTransaction"),
                "true",
            )
            self.assertNodeText(
                request.body, p("Body/CalculateRequest/order/TransactionID"), "0"
            )
            self.assertNodeText(
                request.body, p("Body/CalculateRequest/order/TransactionType"), "01"
            )
            self.assertNodeText(
                request.body, p("Body/CalculateRequest/order/finalize"), "false"
            )
            return True

        self.mock_soap_response(
            rmock=rmock,
            text=self._get_cch_response_ohio_request_short_zip(
                basket.all_lines()[0].id
            ),
            additional_matcher=test_request,
        )

        self.assertFalse(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D("10.00"))

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
        self.assertEqual(shipping_charge.incl_tax, D("14.99"))
        self.assertEqual(len(shipping_charge.components[0].taxation_details), 0)

    @freeze_time("2016-04-13T16:14:44.018599-00:00")
    @requests_mock.mock()
    def test_apply_taxes_nine_digits_postal_code(self, rmock):
        basket = self.prepare_basket_full_zip()
        to_address = self.get_to_address_ohio_full_zip()
        shipping_charge = self.get_shipping_charge()

        def test_request(request):
            self.assertNodeText(
                request.body, p("Body/CalculateRequest/EntityID"), "TESTSANDBOX"
            )
            self.assertNodeText(
                request.body, p("Body/CalculateRequest/DivisionID"), "42"
            )
            self.assertNodeText(
                request.body, p("Body/CalculateRequest/order/CustomerType"), "08"
            )
            self.assertNodeText(
                request.body,
                p("Body/CalculateRequest/order/InvoiceDate"),
                "2016-04-13T12:14:44.018599-04:00",
            )
            self.assertNodeCount(
                request.body, p("Body/CalculateRequest/order/LineItems/LineItem"), 2
            )
            self.assertNodeText(
                request.body,
                p("Body/CalculateRequest/order/LineItems/LineItem[1]/AvgUnitPrice"),
                "10.00000",
            )
            self.assertNodeText(
                request.body,
                p("Body/CalculateRequest/order/LineItems/LineItem[1]/ID"),
                str(basket.all_lines()[0].id),
            )
            self.assertNodeText(
                request.body,
                p(
                    "Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/City"
                ),
                "Anchorage",
            )
            self.assertNodeText(
                request.body,
                p(
                    "Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/CountryCode"
                ),
                "US",
            )
            self.assertNodeText(
                request.body,
                p(
                    "Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/Line1"
                ),
                "325 F st",
            )
            self.assertNodeText(
                request.body,
                p(
                    "Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/PostalCode"
                ),
                "99501",
            )
            self.assertNodeText(
                request.body,
                p(
                    "Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/Plus4"
                ),
                "2217",
            )
            self.assertNodeText(
                request.body,
                p(
                    "Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipFromAddress/StateOrProvince"
                ),
                "AK",
            )
            self.assertNodeText(
                request.body,
                p(
                    "Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/City"
                ),
                "BRINKHAVEN",
            )
            self.assertNodeText(
                request.body,
                p(
                    "Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/CountryCode"
                ),
                "US",
            )
            self.assertNodeText(
                request.body,
                p(
                    "Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/Line1"
                ),
                "200 HIGH ST",
            )
            self.assertNodeText(
                request.body,
                p(
                    "Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/PostalCode"
                ),
                "43006",
            )
            self.assertNodeText(
                request.body,
                p(
                    "Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/Plus4"
                ),
                "9000",
            )
            self.assertNodeText(
                request.body,
                p(
                    "Body/CalculateRequest/order/LineItems/LineItem[1]/NexusInfo/ShipToAddress/StateOrProvince"
                ),
                "OH",
            )
            self.assertNodeText(
                request.body,
                p("Body/CalculateRequest/order/LineItems/LineItem[1]/Quantity"),
                "1",
            )
            self.assertNodeText(
                request.body,
                p("Body/CalculateRequest/order/LineItems/LineItem[1]/SKU"),
                "ABC123",
            )
            self.assertNodeText(
                request.body, p("Body/CalculateRequest/order/ProviderType"), "70"
            )
            self.assertNodeText(
                request.body, p("Body/CalculateRequest/order/SourceSystem"), "Oscar"
            )
            self.assertNodeText(
                request.body,
                p("Body/CalculateRequest/order/TestTransaction"),
                "true",
            )
            self.assertNodeText(
                request.body, p("Body/CalculateRequest/order/TransactionID"), "0"
            )
            self.assertNodeText(
                request.body, p("Body/CalculateRequest/order/TransactionType"), "01"
            )
            self.assertNodeText(
                request.body, p("Body/CalculateRequest/order/finalize"), "false"
            )
            return True

        self.mock_soap_response(
            rmock=rmock,
            text=self._get_cch_response_ohio_request_full_zip(basket.all_lines()[0].id),
            additional_matcher=test_request,
        )

        self.assertFalse(basket.is_tax_known)
        self.assertEqual(basket.total_excl_tax, D("10.00"))

        CCHTaxCalculator().apply_taxes(to_address, basket, shipping_charge)

        self.assertTrue(basket.is_tax_known)
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
        self.assertEqual(shipping_charge.incl_tax, D("14.99"))
        self.assertEqual(len(shipping_charge.components[0].taxation_details), 0)
