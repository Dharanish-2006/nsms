from django.urls import path

from . import views

urlpatterns = [
    path("plants", views.PlantListView.as_view()),
    path("gateways", views.GatewayListView.as_view()),
    path("gateways/<uuid:pk>", views.GatewayDetailView.as_view()),
    path("gateways/<uuid:pk>/rotate-key", views.GatewayRotateKeyView.as_view()),
    path("gateways/<uuid:pk>/users", views.GatewayUsersView.as_view()),
    path("gateways/<uuid:pk>/users/<int:user_id>", views.GatewayUserDetailView.as_view()),
]
