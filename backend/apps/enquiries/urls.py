from django.urls import path

from . import views

urlpatterns = [
    path("contact", views.ContactView.as_view()),
    path("admin-portal/enquiries", views.EnquiryListView.as_view()),
    path("admin-portal/enquiries/<int:pk>", views.EnquiryUpdateView.as_view()),
]
