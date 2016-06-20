from django.test import TestCase
from oscar.core.loading import get_model, get_class
from oscar.test import factories
from decimal import Decimal as D
import time

from oscarcch import cache

Basket = get_model('basket', 'Basket')
USStrategy = get_class('partner.strategy', 'US')


class BasketUATCachingTest(TestCase):
    def test_basic(self):
        product = factories.create_product()
        record = factories.create_stockrecord(
            currency='USD',
            product=product,
            price_excl_tax=D('10.00'))
        factories.create_purchase_info(record)

        basket = Basket()
        basket.strategy = USStrategy()
        basket.add(product)
        basket.save()

        uat1 = cache.get_basket_uat(basket)
        time.sleep(0.5)

        # Nothing has changed, so timestamp should be the same as last time we called it
        uat2 = cache.get_basket_uat(basket)
        self.assertEqual(uat2, uat1)

        # Manually bump the timestamp
        cache.update_basket_uat(basket)
        uat3 = cache.get_basket_uat(basket)
        self.assertTrue(uat3 > uat1)

    def test_multi_baskets(self):
        product = factories.create_product()
        record = factories.create_stockrecord(
            currency='USD',
            product=product,
            price_excl_tax=D('10.00'))
        factories.create_purchase_info(record)

        basket1 = Basket()
        basket1.strategy = USStrategy()
        basket1.add(product)
        basket1.save()

        basket2 = Basket()
        basket2.strategy = USStrategy()
        basket2.add(product)
        basket2.save()

        uat11 = cache.get_basket_uat(basket1)
        uat21 = cache.get_basket_uat(basket2)
        time.sleep(0.25)

        # Nothing has changed, so timestamp should be the same as last time we called it
        uat12 = cache.get_basket_uat(basket1)
        uat22 = cache.get_basket_uat(basket2)
        self.assertEqual(uat12, uat11)
        self.assertEqual(uat22, uat21)

        # Manually bump one of the timestamps
        cache.update_basket_uat(basket2)
        uat13 = cache.get_basket_uat(basket1)
        uat23 = cache.get_basket_uat(basket2)
        self.assertEqual(uat13, uat11)
        self.assertTrue(uat23 > uat13)

        time.sleep(0.25)

        # Manually bump the other timestamp
        cache.update_basket_uat(basket1)
        uat14 = cache.get_basket_uat(basket1)
        uat24 = cache.get_basket_uat(basket2)
        self.assertTrue(uat14 > uat11)
        self.assertEqual(uat24, uat23)

    def test_signals(self):
        product = factories.create_product()
        record = factories.create_stockrecord(
            currency='USD',
            product=product,
            price_excl_tax=D('10.00'))
        factories.create_purchase_info(record)

        basket = Basket()
        basket.strategy = USStrategy()
        basket.add(product)
        basket.save()

        uat1 = cache.get_basket_uat(basket)

        # Add another product
        basket.add(product)

        # Timestamp should have gotten bumped by the BasketLine postsave signal
        uat2 = cache.get_basket_uat(basket)
        self.assertTrue(uat2 > uat1)

        # Save the basket
        basket.save()

        # Timestamp should have gotten bumped by the Basket postsave signal
        uat3 = cache.get_basket_uat(basket)
        self.assertTrue(uat3 > uat2)
