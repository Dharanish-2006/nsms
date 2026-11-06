from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "api/",
        include(
            [
                path("", include("apps.accounts.urls")),
                path("", include("apps.plants.urls")),
                path("", include("apps.telemetry.urls")),
                path("", include("apps.alerts.urls")),
            ]
        ),
    ),
]
