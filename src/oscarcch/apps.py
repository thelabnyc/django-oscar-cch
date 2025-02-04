from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CCHConfig(AppConfig):
    name = "oscarcch"
    label = "cch"
    # Translators: Backend Library Name
    verbose_name = _("CCH Sales Tax Office")
    default = True

    def ready(self) -> None:
        from . import prices  # NOQA

        prices.monkey_patch_prices()
