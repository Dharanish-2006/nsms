from django.urls import path

from . import views

urlpatterns = [
    path("plants", views.PlantListView.as_view()),
    path("gateways/provision", views.GatewayProvisionView.as_view()),
]
