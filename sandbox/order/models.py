from cch.mixins import CCHOrderMixin, CCHOrderLineMixin
from oscar.apps.order.abstract_models import AbstractOrder, AbstractLine

class Order(CCHOrderMixin, AbstractOrder):
    pass

class Line(CCHOrderLineMixin, AbstractLine):
    pass

from oscar.apps.order.models import *  # noqa
