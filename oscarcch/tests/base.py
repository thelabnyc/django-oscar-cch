from decimal import Decimal as D
import re

from django.test import TestCase
from lxml import etree
from oscar.core.loading import get_class, get_model
from oscar.test import factories

from ..prices import ShippingCharge

Basket = get_model("basket", "Basket")
ShippingAddress = get_model("order", "ShippingAddress")
Country = get_model("address", "Country")
PartnerAddress = get_model("partner", "PartnerAddress")
USStrategy = get_class("partner.strategy", "US")


def p(xin):
    """Build a prefix independent XPath"""
    xout = []
    for seg in xin.split("/"):
        # Match segments like "LineItems" and "LineItem[1]"
        matches = re.match(r"^(?P<name>\w+)(\[(?P<index>\d+)\])?", seg)
        xpath_seg = "*[local-name()='%s']" % matches.group("name")
        if matches.group("index"):
            xpath_seg += "[position() = %s]" % matches.group("index")
        xout.append(xpath_seg)
    return "/".join(xout)


class BaseTest(TestCase):
    def setUp(self):
        super().setUp()
        Country.objects.create(
            iso_3166_1_a2="US",
            is_shipping_country=True,
            iso_3166_1_a3="USA",
            iso_3166_1_numeric="840",
            display_order=0,
            name="United States of America",
            printable_name="United States",
        )

    def assertNodeCount(self, xml_str, xpath, num):
        """
        Assert that N number of the given node exist.

        :param xml_str: XML to test
        :param xpath: XPath query to run
        :param num: Number of nodes that the XPath query should return
        """
        doc = etree.fromstring(xml_str)
        nodes = doc.xpath(xpath)
        self.assertEqual(num, len(nodes))

    def assertNodeText(self, xml_str, xpath, expected):
        """
        Assert that each node returned by the XPath equals the given text.

        :param xml_str: XML to test
        :param xpath: XPath query to run
        :param expected: Expected string content
        """
        doc = etree.fromstring(xml_str)
        nodes = doc.xpath(xpath)
        self.assertTrue(len(nodes) > 0)
        for node in nodes:
            self.assertEqual(expected, node.text)

    def prepare_basket(self, lines=1):
        basket = Basket()
        basket.strategy = USStrategy()

        for i in range(lines):
            product = factories.create_product()
            record = factories.create_stockrecord(
                currency="USD", product=product, price=D("10.00")
            )
            factories.create_purchase_info(record)
            basket.add(product)

        from_address = PartnerAddress()
        from_address.line1 = "221 Baker st"
        from_address.line2 = "B"
        from_address.line4 = "Anchorage"
        from_address.state = "AK"
        from_address.postcode = "99501"
        from_address.country = Country.objects.get(pk="US")
        from_address.partner = record.partner
        from_address.save()
        return basket

    def prepare_basket_full_zip(self, lines=1):
        basket = Basket()
        basket.strategy = USStrategy()

        for i in range(lines):
            product = factories.create_product()
            record = factories.create_stockrecord(
                currency="USD", product=product, price=D("10.00")
            )
            factories.create_purchase_info(record)
            basket.add(product)

        from_address = PartnerAddress()
        from_address.line1 = "325 F st"
        from_address.line2 = ""
        from_address.line4 = "Anchorage"
        from_address.state = "AK"
        from_address.postcode = "99501-2217"
        from_address.country = Country.objects.get(pk="US")
        from_address.partner = record.partner
        from_address.save()
        return basket

    def get_to_address_ohio_short_zip(self):
        to_address = ShippingAddress()
        to_address.line1 = "33001 STATE ROUTE 206"
        to_address.line2 = ""
        to_address.line4 = "BRINKHAVEN"
        to_address.state = "OH"
        to_address.postcode = "43006"
        to_address.country = Country.objects.get(pk="US")
        to_address.save()
        return to_address

    def get_to_address_ohio_full_zip(self):
        to_address = ShippingAddress()
        to_address.line1 = "200 HIGH ST"
        to_address.line2 = ""
        to_address.line4 = "BRINKHAVEN"
        to_address.state = "OH"
        to_address.postcode = "43006-9000"
        to_address.country = Country.objects.get(pk="US")
        to_address.save()
        return to_address

    def get_to_address(self):
        to_address = ShippingAddress()
        to_address.line1 = "123 Evergreen Terrace"
        to_address.line2 = "Apt #1"
        to_address.line4 = "Brooklyn"
        to_address.state = "NY"
        to_address.postcode = "11201"
        to_address.country = Country.objects.get(pk="US")
        to_address.save()
        return to_address

    def get_shipping_charge(self):
        return ShippingCharge("USD", D("14.99"))

    def mock_soap_response(self, rmock, *args, **kwargs):
        rmock.register_uri("GET", re.compile(r"^file://"), real_http=True)
        rmock.register_uri("POST", re.compile(r"testserver"), *args, **kwargs)

    def _get_cch_response_normal(self, line_id):
        resp = (
            """
            <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
                <s:Body>
                    <CalculateRequestResponse xmlns="http://schemas.cch.com/STOService/3.5">
                        <CalculateRequestResult xmlns:a="http://schemas.cch.com/TaxResponse/3.5" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
                            <a:LineItemTaxes xmlns:b="http://schemas.cch.com/LineItemTax/3.5">
                                <b:LineItemTax>
                                    <b:CountryCode>US</b:CountryCode>
                                    <b:ID>"""
            + str(line_id)
            + """</b:ID>
                                    <b:StateOrProvince>NY</b:StateOrProvince>
                                    <b:TaxDetails xmlns:c="http://schemas.cch.com/TaxDetail/3.5">
                                        <c:TaxDetail>
                                            <c:AuthorityName>NEW YORK, STATE OF</c:AuthorityName>
                                            <c:AuthorityType>1</c:AuthorityType>
                                            <c:BaseType>00</c:BaseType>
                                            <c:ExemptAmt>0.000</c:ExemptAmt>
                                            <c:ExemptQty>0.00000000</c:ExemptQty>
                                            <c:FeeApplied>0.000000</c:FeeApplied>
                                            <c:PassFlag>1</c:PassFlag>
                                            <c:PassType>00</c:PassType>
                                            <c:TaxApplied>0.40</c:TaxApplied>
                                            <c:TaxName>STATE SALES TAX-GENERAL MERCHANDISE</c:TaxName>
                                            <c:TaxRate>0.040000000000</c:TaxRate>
                                            <c:TaxableAmount>10.000</c:TaxableAmount>
                                            <c:TaxableQuantity>0.00000000</c:TaxableQuantity>
                                        </c:TaxDetail>
                                        <c:TaxDetail>
                                            <c:AuthorityName>NEW YORK, CITY OF</c:AuthorityName>
                                            <c:AuthorityType>3</c:AuthorityType>
                                            <c:BaseType>00</c:BaseType>
                                            <c:ExemptAmt>0.000</c:ExemptAmt>
                                            <c:ExemptQty>0.00000000</c:ExemptQty>
                                            <c:FeeApplied>0.000000</c:FeeApplied>
                                            <c:PassFlag>1</c:PassFlag>
                                            <c:PassType>00</c:PassType>
                                            <c:TaxApplied>0.45</c:TaxApplied>
                                            <c:TaxName>COUNTY SALES TAX-GENERAL MERCHANDISE</c:TaxName>
                                            <c:TaxRate>0.045000000000</c:TaxRate>
                                            <c:TaxableAmount>10.000</c:TaxableAmount>
                                            <c:TaxableQuantity>0.00000000</c:TaxableQuantity>
                                        </c:TaxDetail>
                                        <c:TaxDetail>
                                            <c:AuthorityName>METROPOLITAN TRANSPORTATION AUTHORITY</c:AuthorityName>
                                            <c:AuthorityType>4</c:AuthorityType>
                                            <c:BaseType>00</c:BaseType>
                                            <c:ExemptAmt>0.000</c:ExemptAmt>
                                            <c:ExemptQty>0.00000000</c:ExemptQty>
                                            <c:FeeApplied>0.000000</c:FeeApplied>
                                            <c:PassFlag>1</c:PassFlag>
                                            <c:PassType>00</c:PassType>
                                            <c:TaxApplied>0.04</c:TaxApplied>
                                            <c:TaxName>COUNTY LOCAL SALES TAX-GENERAL MERCHANDISE</c:TaxName>
                                            <c:TaxRate>0.003750000000</c:TaxRate>
                                            <c:TaxableAmount>10.000</c:TaxableAmount>
                                            <c:TaxableQuantity>0.00000000</c:TaxableQuantity>
                                        </c:TaxDetail>
                                    </b:TaxDetails>
                                    <b:TotalTaxApplied>0.89</b:TotalTaxApplied>
                                </b:LineItemTax>
                                <b:LineItemTax>
                                    <b:CountryCode>US</b:CountryCode>
                                    <b:ID>shipping:PARCEL:0</b:ID>
                                    <b:StateOrProvince>NY</b:StateOrProvince>
                                    <b:TaxDetails xmlns:c="http://schemas.cch.com/TaxDetail/3.5">
                                        <c:TaxDetail>
                                            <c:AuthorityName>NEW YORK, STATE OF</c:AuthorityName>
                                            <c:AuthorityType>1</c:AuthorityType>
                                            <c:BaseType>00</c:BaseType>
                                            <c:ExemptAmt>0.000</c:ExemptAmt>
                                            <c:ExemptQty>0.00000000</c:ExemptQty>
                                            <c:FeeApplied>0.000000</c:FeeApplied>
                                            <c:PassFlag>1</c:PassFlag>
                                            <c:PassType>00</c:PassType>
                                            <c:TaxApplied>0.5996</c:TaxApplied>
                                            <c:TaxName>STATE SALES TAX-GENERAL MERCHANDISE</c:TaxName>
                                            <c:TaxRate>0.040000000000</c:TaxRate>
                                            <c:TaxableAmount>14.990</c:TaxableAmount>
                                            <c:TaxableQuantity>0.00000000</c:TaxableQuantity>
                                        </c:TaxDetail>
                                        <c:TaxDetail>
                                            <c:AuthorityName>NEW YORK, CITY OF</c:AuthorityName>
                                            <c:AuthorityType>3</c:AuthorityType>
                                            <c:BaseType>00</c:BaseType>
                                            <c:ExemptAmt>0.000</c:ExemptAmt>
                                            <c:ExemptQty>0.00000000</c:ExemptQty>
                                            <c:FeeApplied>0.000000</c:FeeApplied>
                                            <c:PassFlag>1</c:PassFlag>
                                            <c:PassType>00</c:PassType>
                                            <c:TaxApplied>0.67455</c:TaxApplied>
                                            <c:TaxName>COUNTY SALES TAX-GENERAL MERCHANDISE</c:TaxName>
                                            <c:TaxRate>0.045000000000</c:TaxRate>
                                            <c:TaxableAmount>14.990</c:TaxableAmount>
                                            <c:TaxableQuantity>0.00000000</c:TaxableQuantity>
                                        </c:TaxDetail>
                                        <c:TaxDetail>
                                            <c:AuthorityName>METROPOLITAN TRANSPORTATION AUTHORITY</c:AuthorityName>
                                            <c:AuthorityType>4</c:AuthorityType>
                                            <c:BaseType>00</c:BaseType>
                                            <c:ExemptAmt>0.000</c:ExemptAmt>
                                            <c:ExemptQty>0.00000000</c:ExemptQty>
                                            <c:FeeApplied>0.000000</c:FeeApplied>
                                            <c:PassFlag>1</c:PassFlag>
                                            <c:PassType>00</c:PassType>
                                            <c:TaxApplied>0.0562125</c:TaxApplied>
                                            <c:TaxName>COUNTY LOCAL SALES TAX-GENERAL MERCHANDISE</c:TaxName>
                                            <c:TaxRate>0.003750000000</c:TaxRate>
                                            <c:TaxableAmount>14.990</c:TaxableAmount>
                                            <c:TaxableQuantity>0.00000000</c:TaxableQuantity>
                                        </c:TaxDetail>
                                    </b:TaxDetails>
                                    <b:TotalTaxApplied>1.3303625</b:TotalTaxApplied>
                                </b:LineItemTax>
                            </a:LineItemTaxes>
                            <a:Messages i:nil="true" xmlns:b="http://schemas.cch.com/Message/3.5"/>
                            <a:TotalTaxApplied>2.2203625</a:TotalTaxApplied>
                            <a:TransactionID>40043</a:TransactionID>
                            <a:TransactionStatus>4</a:TransactionStatus>
                        </CalculateRequestResult>
                    </CalculateRequestResponse>
                </s:Body>
            </s:Envelope>"""
        )
        return resp

    def _get_cch_response_basket_only(self, line_id):
        resp = (
            """
            <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
                <s:Body>
                    <CalculateRequestResponse xmlns="http://schemas.cch.com/STOService/3.5">
                        <CalculateRequestResult xmlns:a="http://schemas.cch.com/TaxResponse/3.5" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
                            <a:LineItemTaxes xmlns:b="http://schemas.cch.com/LineItemTax/3.5">
                                <b:LineItemTax>
                                    <b:CountryCode>US</b:CountryCode>
                                    <b:ID>"""
            + str(line_id)
            + """</b:ID>
                                    <b:StateOrProvince>NY</b:StateOrProvince>
                                    <b:TaxDetails xmlns:c="http://schemas.cch.com/TaxDetail/3.5">
                                        <c:TaxDetail>
                                            <c:AuthorityName>NEW YORK, STATE OF</c:AuthorityName>
                                            <c:AuthorityType>1</c:AuthorityType>
                                            <c:BaseType>00</c:BaseType>
                                            <c:ExemptAmt>0.000</c:ExemptAmt>
                                            <c:ExemptQty>0.00000000</c:ExemptQty>
                                            <c:FeeApplied>0.000000</c:FeeApplied>
                                            <c:PassFlag>1</c:PassFlag>
                                            <c:PassType>00</c:PassType>
                                            <c:TaxApplied>0.40</c:TaxApplied>
                                            <c:TaxName>STATE SALES TAX-GENERAL MERCHANDISE</c:TaxName>
                                            <c:TaxRate>0.040000000000</c:TaxRate>
                                            <c:TaxableAmount>10.000</c:TaxableAmount>
                                            <c:TaxableQuantity>0.00000000</c:TaxableQuantity>
                                        </c:TaxDetail>
                                        <c:TaxDetail>
                                            <c:AuthorityName>NEW YORK, CITY OF</c:AuthorityName>
                                            <c:AuthorityType>3</c:AuthorityType>
                                            <c:BaseType>00</c:BaseType>
                                            <c:ExemptAmt>0.000</c:ExemptAmt>
                                            <c:ExemptQty>0.00000000</c:ExemptQty>
                                            <c:FeeApplied>0.000000</c:FeeApplied>
                                            <c:PassFlag>1</c:PassFlag>
                                            <c:PassType>00</c:PassType>
                                            <c:TaxApplied>0.45</c:TaxApplied>
                                            <c:TaxName>COUNTY SALES TAX-GENERAL MERCHANDISE</c:TaxName>
                                            <c:TaxRate>0.045000000000</c:TaxRate>
                                            <c:TaxableAmount>10.000</c:TaxableAmount>
                                            <c:TaxableQuantity>0.00000000</c:TaxableQuantity>
                                        </c:TaxDetail>
                                        <c:TaxDetail>
                                            <c:AuthorityName>METROPOLITAN TRANSPORTATION AUTHORITY</c:AuthorityName>
                                            <c:AuthorityType>4</c:AuthorityType>
                                            <c:BaseType>00</c:BaseType>
                                            <c:ExemptAmt>0.000</c:ExemptAmt>
                                            <c:ExemptQty>0.00000000</c:ExemptQty>
                                            <c:FeeApplied>0.000000</c:FeeApplied>
                                            <c:PassFlag>1</c:PassFlag>
                                            <c:PassType>00</c:PassType>
                                            <c:TaxApplied>0.04</c:TaxApplied>
                                            <c:TaxName>COUNTY LOCAL SALES TAX-GENERAL MERCHANDISE</c:TaxName>
                                            <c:TaxRate>0.003750000000</c:TaxRate>
                                            <c:TaxableAmount>10.000</c:TaxableAmount>
                                            <c:TaxableQuantity>0.00000000</c:TaxableQuantity>
                                        </c:TaxDetail>
                                    </b:TaxDetails>
                                    <b:TotalTaxApplied>0.89</b:TotalTaxApplied>
                                </b:LineItemTax>
                            </a:LineItemTaxes>
                            <a:Messages i:nil="true" xmlns:b="http://schemas.cch.com/Message/3.5"/>
                            <a:TotalTaxApplied>2.2203625</a:TotalTaxApplied>
                            <a:TransactionID>40043</a:TransactionID>
                            <a:TransactionStatus>4</a:TransactionStatus>
                        </CalculateRequestResult>
                    </CalculateRequestResponse>
                </s:Body>
            </s:Envelope>"""
        )
        return resp

    def _get_cch_response_shipping_only(self):
        resp = """
            <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
                <s:Body>
                    <CalculateRequestResponse xmlns="http://schemas.cch.com/STOService/3.5">
                        <CalculateRequestResult xmlns:a="http://schemas.cch.com/TaxResponse/3.5" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
                            <a:LineItemTaxes xmlns:b="http://schemas.cch.com/LineItemTax/3.5">
                                <b:LineItemTax>
                                    <b:CountryCode>US</b:CountryCode>
                                    <b:ID>shipping:PARCEL:0</b:ID>
                                    <b:StateOrProvince>NY</b:StateOrProvince>
                                    <b:TaxDetails xmlns:c="http://schemas.cch.com/TaxDetail/3.5">
                                        <c:TaxDetail>
                                            <c:AuthorityName>NEW YORK, STATE OF</c:AuthorityName>
                                            <c:AuthorityType>1</c:AuthorityType>
                                            <c:BaseType>00</c:BaseType>
                                            <c:ExemptAmt>0.000</c:ExemptAmt>
                                            <c:ExemptQty>0.00000000</c:ExemptQty>
                                            <c:FeeApplied>0.000000</c:FeeApplied>
                                            <c:PassFlag>1</c:PassFlag>
                                            <c:PassType>00</c:PassType>
                                            <c:TaxApplied>0.5996</c:TaxApplied>
                                            <c:TaxName>STATE SALES TAX-GENERAL MERCHANDISE</c:TaxName>
                                            <c:TaxRate>0.040000000000</c:TaxRate>
                                            <c:TaxableAmount>14.990</c:TaxableAmount>
                                            <c:TaxableQuantity>0.00000000</c:TaxableQuantity>
                                        </c:TaxDetail>
                                        <c:TaxDetail>
                                            <c:AuthorityName>NEW YORK, CITY OF</c:AuthorityName>
                                            <c:AuthorityType>3</c:AuthorityType>
                                            <c:BaseType>00</c:BaseType>
                                            <c:ExemptAmt>0.000</c:ExemptAmt>
                                            <c:ExemptQty>0.00000000</c:ExemptQty>
                                            <c:FeeApplied>0.000000</c:FeeApplied>
                                            <c:PassFlag>1</c:PassFlag>
                                            <c:PassType>00</c:PassType>
                                            <c:TaxApplied>0.67455</c:TaxApplied>
                                            <c:TaxName>COUNTY SALES TAX-GENERAL MERCHANDISE</c:TaxName>
                                            <c:TaxRate>0.045000000000</c:TaxRate>
                                            <c:TaxableAmount>14.990</c:TaxableAmount>
                                            <c:TaxableQuantity>0.00000000</c:TaxableQuantity>
                                        </c:TaxDetail>
                                        <c:TaxDetail>
                                            <c:AuthorityName>METROPOLITAN TRANSPORTATION AUTHORITY</c:AuthorityName>
                                            <c:AuthorityType>4</c:AuthorityType>
                                            <c:BaseType>00</c:BaseType>
                                            <c:ExemptAmt>0.000</c:ExemptAmt>
                                            <c:ExemptQty>0.00000000</c:ExemptQty>
                                            <c:FeeApplied>0.000000</c:FeeApplied>
                                            <c:PassFlag>1</c:PassFlag>
                                            <c:PassType>00</c:PassType>
                                            <c:TaxApplied>0.0562125</c:TaxApplied>
                                            <c:TaxName>COUNTY LOCAL SALES TAX-GENERAL MERCHANDISE</c:TaxName>
                                            <c:TaxRate>0.003750000000</c:TaxRate>
                                            <c:TaxableAmount>14.990</c:TaxableAmount>
                                            <c:TaxableQuantity>0.00000000</c:TaxableQuantity>
                                        </c:TaxDetail>
                                    </b:TaxDetails>
                                    <b:TotalTaxApplied>1.3303625</b:TotalTaxApplied>
                                </b:LineItemTax>
                            </a:LineItemTaxes>
                            <a:Messages i:nil="true" xmlns:b="http://schemas.cch.com/Message/3.5"/>
                            <a:TotalTaxApplied>1.3303625</a:TotalTaxApplied>
                            <a:TransactionID>40043</a:TransactionID>
                            <a:TransactionStatus>4</a:TransactionStatus>
                        </CalculateRequestResult>
                    </CalculateRequestResponse>
                </s:Body>
            </s:Envelope>"""
        return resp

    def _get_cch_response_shipping_only_multiple_skus(self):
        resp = """
            <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
                <s:Body>
                    <CalculateRequestResponse xmlns="http://schemas.cch.com/STOService/3.5">
                        <CalculateRequestResult xmlns:a="http://schemas.cch.com/TaxResponse/3.5" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
                            <a:LineItemTaxes xmlns:b="http://schemas.cch.com/LineItemTax/3.5">
                                <b:LineItemTax>
                                    <b:CountryCode>US</b:CountryCode>
                                    <b:ID>shipping:FREIGHT:0</b:ID>
                                    <b:StateOrProvince>NY</b:StateOrProvince>
                                    <b:TaxDetails xmlns:c="http://schemas.cch.com/TaxDetail/3.5">
                                        <c:TaxDetail>
                                            <c:AuthorityName>NEW YORK, STATE OF</c:AuthorityName>
                                            <c:AuthorityType>1</c:AuthorityType>
                                            <c:BaseType>00</c:BaseType>
                                            <c:ExemptAmt>0.000</c:ExemptAmt>
                                            <c:ExemptQty>0.00000000</c:ExemptQty>
                                            <c:FeeApplied>0.000000</c:FeeApplied>
                                            <c:PassFlag>1</c:PassFlag>
                                            <c:PassType>00</c:PassType>
                                            <c:TaxApplied>4.00</c:TaxApplied>
                                            <c:TaxName>STATE SALES TAX-GENERAL MERCHANDISE</c:TaxName>
                                            <c:TaxRate>0.040000000000</c:TaxRate>
                                            <c:TaxableAmount>100.00</c:TaxableAmount>
                                            <c:TaxableQuantity>0.00000000</c:TaxableQuantity>
                                        </c:TaxDetail>
                                    </b:TaxDetails>
                                    <b:TotalTaxApplied>4.00</b:TotalTaxApplied>
                                </b:LineItemTax>
                                <b:LineItemTax>
                                    <b:CountryCode>US</b:CountryCode>
                                    <b:ID>shipping:UPS:1</b:ID>
                                    <b:StateOrProvince>NY</b:StateOrProvince>
                                    <b:TaxDetails xmlns:c="http://schemas.cch.com/TaxDetail/3.5">
                                        <c:TaxDetail>
                                            <c:AuthorityName>NEW YORK, STATE OF</c:AuthorityName>
                                            <c:AuthorityType>1</c:AuthorityType>
                                            <c:BaseType>00</c:BaseType>
                                            <c:ExemptAmt>0.000</c:ExemptAmt>
                                            <c:ExemptQty>0.00000000</c:ExemptQty>
                                            <c:FeeApplied>0.000000</c:FeeApplied>
                                            <c:PassFlag>1</c:PassFlag>
                                            <c:PassType>00</c:PassType>
                                            <c:TaxApplied>0.80</c:TaxApplied>
                                            <c:TaxName>STATE SALES TAX-GENERAL MERCHANDISE</c:TaxName>
                                            <c:TaxRate>0.040000000000</c:TaxRate>
                                            <c:TaxableAmount>20.00</c:TaxableAmount>
                                            <c:TaxableQuantity>0.00000000</c:TaxableQuantity>
                                        </c:TaxDetail>
                                    </b:TaxDetails>
                                    <b:TotalTaxApplied>0.80</b:TotalTaxApplied>
                                </b:LineItemTax>
                            </a:LineItemTaxes>
                            <a:Messages i:nil="true" xmlns:b="http://schemas.cch.com/Message/3.5"/>
                            <a:TotalTaxApplied>4.80</a:TotalTaxApplied>
                            <a:TransactionID>40043</a:TransactionID>
                            <a:TransactionStatus>4</a:TransactionStatus>
                        </CalculateRequestResult>
                    </CalculateRequestResponse>
                </s:Body>
            </s:Envelope>"""
        return resp

    def _get_cch_response_ohio_request_short_zip(self, line_id):
        resp = (
            """
        <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
            <s:Body>
                <CalculateRequestResponse xmlns="http://schemas.cch.com/STOService/3.5">
                    <CalculateRequestResult xmlns:a="http://schemas.cch.com/TaxResponse/3.5" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
                        <a:LineItemTaxes xmlns:b="http://schemas.cch.com/LineItemTax/3.5">
                            <b:LineItemTax>
                                <b:CountryCode>US</b:CountryCode>
                                <b:ID>"""
            + str(line_id)
            + """</b:ID>
                                <b:StateOrProvince>OH</b:StateOrProvince>
                                <b:TaxDetails xmlns:c="http://schemas.cch.com/TaxDetail/3.5">
                                    <c:TaxDetail>
                                        <c:AuthorityName>OHIO, STATE OF</c:AuthorityName>
                                        <c:AuthorityType>1</c:AuthorityType>
                                        <c:BaseType>00</c:BaseType>
                                        <c:ExemptAmt>0.000</c:ExemptAmt>
                                        <c:ExemptQty>0.00000000</c:ExemptQty>
                                        <c:FeeApplied>0.000000</c:FeeApplied>
                                        <c:PassFlag>1</c:PassFlag>
                                        <c:PassType>00</c:PassType>
                                        <c:TaxApplied>0.58</c:TaxApplied>
                                        <c:TaxName>STATE SALES TAX-GENERAL MERCHANDISE</c:TaxName>
                                        <c:TaxRate>0.057500000000</c:TaxRate>
                                        <c:TaxableAmount>10.000</c:TaxableAmount>
                                        <c:TaxableQuantity>0.00000000</c:TaxableQuantity>
                                    </c:TaxDetail>
                                    <c:TaxDetail>
                                        <c:AuthorityName>KNOX, COUNTY OF</c:AuthorityName>
                                        <c:AuthorityType>2</c:AuthorityType>
                                        <c:BaseType>00</c:BaseType>
                                        <c:ExemptAmt>0.000</c:ExemptAmt>
                                        <c:ExemptQty>0.00000000</c:ExemptQty>
                                        <c:FeeApplied>0.000000</c:FeeApplied>
                                        <c:PassFlag>1</c:PassFlag>
                                        <c:PassType>00</c:PassType>
                                        <c:TaxApplied>0.10</c:TaxApplied>
                                        <c:TaxName>COUNTY SALES TAX-GENERAL MERCHANDISE</c:TaxName>
                                        <c:TaxRate>0.010000000000</c:TaxRate>
                                        <c:TaxableAmount>10.000</c:TaxableAmount>
                                        <c:TaxableQuantity>0.00000000</c:TaxableQuantity>
                                    </c:TaxDetail>
                                </b:TaxDetails>
                                <b:TotalTaxApplied>0.68</b:TotalTaxApplied>
                            </b:LineItemTax>
                        </a:LineItemTaxes>
                        <a:Messages i:nil="true" xmlns:b="http://schemas.cch.com/Message/3.5"/>
                        <a:TotalTaxApplied>0.68</a:TotalTaxApplied>
                        <a:TransactionID>121424</a:TransactionID>
                        <a:TransactionStatus>4</a:TransactionStatus>
                    </CalculateRequestResult>
                </CalculateRequestResponse>
            </s:Body>
        </s:Envelope>
        """
        )
        return resp

    def _get_cch_response_ohio_request_full_zip(self, line_id):
        resp = (
            """
        <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
            <s:Body>
                <CalculateRequestResponse xmlns="http://schemas.cch.com/STOService/3.5">
                    <CalculateRequestResult xmlns:a="http://schemas.cch.com/TaxResponse/3.5" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
                        <a:LineItemTaxes xmlns:b="http://schemas.cch.com/LineItemTax/3.5">
                            <b:LineItemTax>
                                <b:CountryCode>US</b:CountryCode>
                                <b:ID>"""
            + str(line_id)
            + """</b:ID>
                                <b:StateOrProvince>OH</b:StateOrProvince>
                                <b:TaxDetails xmlns:c="http://schemas.cch.com/TaxDetail/3.5">
                                    <c:TaxDetail>
                                        <c:AuthorityName>OHIO, STATE OF</c:AuthorityName>
                                        <c:AuthorityType>1</c:AuthorityType>
                                        <c:BaseType>00</c:BaseType>
                                        <c:ExemptAmt>0.000</c:ExemptAmt>
                                        <c:ExemptQty>0.00000000</c:ExemptQty>
                                        <c:FeeApplied>0.000000</c:FeeApplied>
                                        <c:PassFlag>1</c:PassFlag>
                                        <c:PassType>00</c:PassType>
                                        <c:TaxApplied>0.58</c:TaxApplied>
                                        <c:TaxName>STATE SALES TAX-GENERAL MERCHANDISE</c:TaxName>
                                        <c:TaxRate>0.057500000000</c:TaxRate>
                                        <c:TaxableAmount>10.000</c:TaxableAmount>
                                        <c:TaxableQuantity>0.00000000</c:TaxableQuantity>
                                    </c:TaxDetail><c:TaxDetail>
                                        <c:AuthorityName>COSHOCTON, COUNTY OF</c:AuthorityName>
                                        <c:AuthorityType>2</c:AuthorityType>
                                        <c:BaseType>00</c:BaseType>
                                        <c:ExemptAmt>0.000</c:ExemptAmt>
                                        <c:ExemptQty>0.00000000</c:ExemptQty>
                                        <c:FeeApplied>0.000000</c:FeeApplied>
                                        <c:PassFlag>1</c:PassFlag>
                                        <c:PassType>00</c:PassType>
                                        <c:TaxApplied>0.15</c:TaxApplied>
                                        <c:TaxName>COUNTY SALES TAX-GENERAL MERCHANDISE</c:TaxName>
                                        <c:TaxRate>0.015000000000</c:TaxRate>
                                        <c:TaxableAmount>10.000</c:TaxableAmount>
                                        <c:TaxableQuantity>0.00000000</c:TaxableQuantity>
                                    </c:TaxDetail>
                                </b:TaxDetails>
                                <b:TotalTaxApplied>0.73</b:TotalTaxApplied>
                            </b:LineItemTax>
                        </a:LineItemTaxes>
                        <a:Messages i:nil="true" xmlns:b="http://schemas.cch.com/Message/3.5"/>
                        <a:TotalTaxApplied>0.73</a:TotalTaxApplied>
                        <a:TransactionID>121425</a:TransactionID>
                        <a:TransactionStatus>4</a:TransactionStatus>
                    </CalculateRequestResult>
                </CalculateRequestResponse>
            </s:Body>
        </s:Envelope>
        """
        )
        return resp

    def _get_cch_response_empty(self):
        resp = """
            <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
                <s:Body>
                    <CalculateRequestResponse xmlns="http://schemas.cch.com/STOService/3.5">
                        <CalculateRequestResult xmlns:a="http://schemas.cch.com/TaxResponse/3.5" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
                            <a:LineItemTaxes xmlns:b="http://schemas.cch.com/LineItemTax/3.5"/>
                            <a:Messages xmlns:b="http://schemas.cch.com/Message/3.5">
                                <b:Message>
                                    <b:Code>0</b:Code>
                                    <b:Info>OK</b:Info>
                                    <b:Reference i:nil="true"></b:Reference>
                                    <b:Severity>0</b:Severity>
                                    <b:Source>0</b:Source>
                                    <b:TransactionStatus>4</b:TransactionStatus>
                                </b:Message>
                            </a:Messages>
                            <a:TotalTaxApplied>0.00</a:TotalTaxApplied>
                            <a:TransactionID>40043</a:TransactionID>
                            <a:TransactionStatus>4</a:TransactionStatus>
                        </CalculateRequestResult>
                    </CalculateRequestResponse>
                </s:Body>
            </s:Envelope>"""
        return resp

    def _get_cch_response_db_connection_error(self):
        resp = """
            <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
                <s:Body>
                    <CalculateRequestResponse xmlns="http://schemas.cch.com/STOService/3.5">
                        <CalculateRequestResult xmlns:a="http://schemas.cch.com/TaxResponse/3.5" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
                            <a:LineItemTaxes xmlns:b="http://schemas.cch.com/LineItemTax/3.5"/>
                            <a:Messages xmlns:b="http://schemas.cch.com/Message/3.5">
                                <b:Message>
                                    <b:Code>9999</b:Code>
                                    <b:Info>A network-related or instance-specific error occurred while establishing a connection to SQL Server.</b:Info>
                                    <b:Reference i:nil="true"></b:Reference>
                                    <b:Severity>1</b:Severity>
                                    <b:Source>0</b:Source>
                                    <b:TransactionStatus>1</b:TransactionStatus>
                                </b:Message>
                            </a:Messages>
                            <a:TotalTaxApplied>0.00</a:TotalTaxApplied>
                            <a:TransactionID></a:TransactionID>
                            <a:TransactionStatus>1</a:TransactionStatus>
                        </CalculateRequestResult>
                    </CalculateRequestResponse>
                </s:Body>
            </s:Envelope>"""
        return resp
