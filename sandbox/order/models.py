from oscar.apps.order.abstract_models import AbstractLine, AbstractOrder

from oscarcch.mixins import CCHOrderLineMixin, CCHOrderMixin


class Order(CCHOrderMixin, AbstractOrder):
    pass


class Line(CCHOrderLineMixin, AbstractLine):
    pass


from oscar.apps.order.models import *  # type:ignore[assignment] # noqa
