from cch.mixins import CCHOrderCreatorMixin
from oscar.apps.order import utils


class OrderCreator(CCHOrderCreatorMixin, utils.OrderCreator):
    pass
