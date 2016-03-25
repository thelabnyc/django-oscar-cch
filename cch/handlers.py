from django.db.models.signals import post_save, post_delete
from oscar.core.loading import get_model

from . import cache


Basket = get_model('basket', 'Basket')
BasketLine = get_model('basket', 'Line')


def on_basket_save(sender, instance, **kwargs):
    cache.update_basket_uat(instance)

def on_basket_line_save(sender, instance, **kwargs):
    cache.update_basket_uat(instance.basket)

post_save.connect(on_basket_save, sender=Basket, dispatch_uid="cch_update_basket_uat")
post_save.connect(on_basket_line_save, sender=BasketLine, dispatch_uid="cch_update_basket_line_uat")
post_delete.connect(on_basket_line_save, sender=BasketLine, dispatch_uid="cch_delete_basket_line_uat")
