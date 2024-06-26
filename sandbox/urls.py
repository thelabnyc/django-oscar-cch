from django.apps import apps
from django.conf.urls import patterns, include
from django.urls import path
from django.contrib import admin


urlpatterns = patterns(
    "",
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),
    path("api/", include("oscarapi.urls")),
    path("", include(apps.get_app_config("oscar").urls[0])),
)
