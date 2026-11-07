from django.urls import path

from . import views

urlpatterns = [
    path("alerts", views.AlertListView.as_view()),
    path("thresholds", views.ThresholdListView.as_view()),
    path("thresholds/<int:pk>", views.ThresholdDetailView.as_view()),
    path("phones", views.PhoneListView.as_view()),
    path("phones/<int:pk>", views.PhoneDetailView.as_view()),
    path("settings/notifications", views.NotificationSettingsView.as_view()),
]
