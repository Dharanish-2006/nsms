from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),  # the React Admin Portal owns /admin,
    path(
        "api/",
        include(
            [
                path("", include("apps.accounts.urls")),
                path("", include("apps.plants.urls")),
                path("", include("apps.telemetry.urls")),
                path("", include("apps.alerts.urls")),
                path("", include("apps.adminportal.urls")),
            ]
        ),
    ),
]
