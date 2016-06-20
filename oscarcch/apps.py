from django.apps import AppConfig


class CCHConfig(AppConfig):
    name = 'oscarcch'
    label = 'cch'
    verbose_name = "CCH Sales Tax Office"

    def ready(self):
        from . import handlers, prices  # NOQA
        prices.monkey_patch_fixed_price()
