from oscar.apps.order import utils
from oscar.core.loading import get_class

CCHOrderCreatorMixin = get_class('oscarcch.mixins', 'CCHOrderCreatorMixin')


class OrderCreator(CCHOrderCreatorMixin, utils.OrderCreator):
    pass
