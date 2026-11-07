from django.urls import path

from . import views

urlpatterns = [
    path("healthz", views.health),
    path("ingest", views.IngestView.as_view()),
    path("iot/ingest", views.IotIngestView.as_view()),
    path("machines", views.MachineListView.as_view()),
    path("machines/usage", views.UsageView.as_view()),
    path("machines/<slug:pk>", views.MachineDetailView.as_view()),
    path("machines/<slug:pk>/trend", views.TrendView.as_view()),
    path("reports/daily", views.DailyReportView.as_view()),
]
