from oscar.apps.order import utils

from oscarcch.order_creator import CCHOrderCreatorMixin
from oscarcch.suretax import SureTaxCalculator


class OrderCreator(CCHOrderCreatorMixin, utils.OrderCreator):
    pass


class SureTaxOrderCreator(OrderCreator):
    def get_tax_calculator(self) -> SureTaxCalculator:
        return SureTaxCalculator()
