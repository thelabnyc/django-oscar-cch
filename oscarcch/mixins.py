from django.db import models


class CCHOrderMixin(models.Model):
    is_tax_known = models.BooleanField(default=True)

    class Meta:
        abstract = True


class CCHOrderLineMixin(models.Model):
    basket_line = models.OneToOneField(
        "basket.Line",
        related_name="order_line",
        on_delete=models.SET_NULL,
        null=True,
    )

    class Meta:
        abstract = True
