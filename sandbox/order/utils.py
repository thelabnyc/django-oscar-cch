from oscar.apps.order import utils

from oscarcch.mixins import CCHOrderCreatorMixin


class OrderCreator(CCHOrderCreatorMixin, utils.OrderCreator):
    pass
