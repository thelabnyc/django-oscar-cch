from oscar.apps.order.abstract_models import AbstractOrder, AbstractLine
from oscarcch.mixins import CCHOrderMixin
from oscarcch.mixins import CCHOrderLineMixin


class Order(CCHOrderMixin, AbstractOrder):
    pass


class Line(CCHOrderLineMixin, AbstractLine):
    pass


from oscar.apps.order.models import *  # noqa
