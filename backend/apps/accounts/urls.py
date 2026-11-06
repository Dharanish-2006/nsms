from django.urls import path

from . import views

urlpatterns = [
    path("auth/login", views.LoginView.as_view()),
    path("auth/otp/send", views.OtpSendView.as_view()),
    path("auth/otp/verify", views.OtpVerifyView.as_view()),
    path("auth/register", views.RegisterView.as_view()),
    path("auth/me", views.MeView.as_view()),
    path("auth/logout", views.LogoutView.as_view()),
    path("auth/change-password", views.ChangePasswordView.as_view()),
    path("users", views.UserListView.as_view()),
    path("users/<int:pk>/approve", views.UserApproveView.as_view()),
    path("users/<int:pk>", views.UserDetailView.as_view()),
]
