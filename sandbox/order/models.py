from oscar.apps.order.abstract_models import AbstractOrder, AbstractLine
from oscar.core.loading import get_class

CCHOrderMixin = get_class('oscarcch.mixins', 'CCHOrderMixin')
CCHOrderLineMixin = get_class('oscarcch.mixins', 'CCHOrderLineMixin')


class Order(CCHOrderMixin, AbstractOrder):
    pass


class Line(CCHOrderLineMixin, AbstractLine):
    pass


from oscar.apps.order.models import *  # noqa
