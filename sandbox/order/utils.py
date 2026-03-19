from oscar.apps.order import utils

from oscarcch.order_creator import CCHOrderCreatorMixin


class OrderCreator(CCHOrderCreatorMixin, utils.OrderCreator):
    pass
