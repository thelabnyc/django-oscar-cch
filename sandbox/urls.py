from django.apps import apps
from django.conf.urls import include, patterns
from django.contrib import admin
from django.urls import path

urlpatterns = patterns(
    "",
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),
    path("api/", include("oscarapi.urls")),
    path("", include(apps.get_app_config("oscar").urls[0])),
)
