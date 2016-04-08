from decimal import Decimal as D
from django.test import TestCase
from oscar.core.loading import get_model, get_class
from oscar.test import factories
from soap.tests import SoapTest

Basket = get_model('basket', 'Basket')
ShippingAddress = get_model('order', 'ShippingAddress')
Country = get_model('address', 'Country')
PartnerAddress = get_model('partner', 'PartnerAddress')
USStrategy = get_class('partner.strategy', 'US')



class BaseTest(SoapTest, TestCase):
    def setUp(self):
        super().setUp()
        Country.objects.create(
            iso_3166_1_a2='US',
            is_shipping_country=True,
            iso_3166_1_a3='USA',
            iso_3166_1_numeric='840',
            display_order=0,
            name="United States of America",
            printable_name="United States")


    def prepare_basket(self):
        basket = Basket()
        basket.strategy = USStrategy()
        product = factories.create_product()
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
        return basket


    def get_to_address(self):
        to_address = ShippingAddress()
        to_address.line1 = '123 Evergreen Terrace'
        to_address.line2 = 'Apt #1'
        to_address.line4 = 'Brooklyn'
        to_address.state = 'NY'
        to_address.postcode = '11201'
        to_address.country = Country.objects.get(pk='US')
        to_address.save()
        return to_address


    def _get_cch_response_normal(self, line_id):
        resp = """
            <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
                <s:Body>
                    <CalculateRequestResponse xmlns="http://schemas.cch.com/STOService/3.5">
                        <CalculateRequestResult xmlns:a="http://schemas.cch.com/TaxResponse/3.5" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
                            <a:LineItemTaxes xmlns:b="http://schemas.cch.com/LineItemTax/3.5">
                                <b:LineItemTax>
                                    <b:CountryCode>US</b:CountryCode>
                                    <b:ID>""" + str(line_id) + """</b:ID>
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
                            <a:TotalTaxApplied>0.89</a:TotalTaxApplied>
                            <a:TransactionID>40043</a:TransactionID>
                            <a:TransactionStatus>4</a:TransactionStatus>
                        </CalculateRequestResult>
                    </CalculateRequestResponse>
                </s:Body>
            </s:Envelope>"""
        return resp.encode('utf8')


    def _get_cch_response_empty(self):
        resp = """
            <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
                <s:Body>
                    <CalculateRequestResponse xmlns="http://schemas.cch.com/STOService/3.5">
                        <CalculateRequestResult xmlns:a="http://schemas.cch.com/TaxResponse/3.5" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
                            <a:LineItemTaxes xmlns:b="http://schemas.cch.com/LineItemTax/3.5"/>
                            <a:Messages i:nil="true" xmlns:b="http://schemas.cch.com/Message/3.5"/>
                            <a:TotalTaxApplied>0.00</a:TotalTaxApplied>
                            <a:TransactionID>40043</a:TransactionID>
                            <a:TransactionStatus>4</a:TransactionStatus>
                        </CalculateRequestResult>
                    </CalculateRequestResponse>
                </s:Body>
            </s:Envelope>"""
        return resp.encode('utf8')
