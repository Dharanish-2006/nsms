from django.urls import path

from . import views

urlpatterns = [
    path("admin-portal/dashboard", views.DashboardView.as_view()),
    path("admin-portal/users", views.UserListView.as_view()),
    path("admin-portal/users/<int:pk>/approve", views.UserApproveView.as_view()),
    path("admin-portal/users/<int:pk>/reject", views.UserRejectView.as_view()),
    path("admin-portal/gateways", views.GatewayListView.as_view()),
    path("admin-portal/gateways/<uuid:pk>/rotate-key", views.GatewayRotateKeyView.as_view()),
    path("admin-portal/gateways/<uuid:pk>/machines", views.GatewayMachinesView.as_view()),
    path("admin-portal/assignments", views.AssignmentListView.as_view()),
    path("admin-portal/assignments/<int:pk>/connect", views.AssignmentConnectView.as_view()),
    path("admin-portal/assignments/<int:pk>/disconnect", views.AssignmentDisconnectView.as_view()),
    path("admin-portal/audit-log", views.AuditLogView.as_view()),
]
