from django.apps import apps
from django.conf.urls import patterns, include, url
from django.contrib import admin


urlpatterns = patterns(
    "",
    url(r"^i18n/", include("django.conf.urls.i18n")),
    url(r"^admin/", admin.site.urls),
    url(r"^api/", include("oscarapi.urls")),
    url(r"^", include(apps.get_app_config("oscar").urls[0])),
)
