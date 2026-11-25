"""Massage package pages. Included under /admin/packages/, so only Admins and the Super Admin reach them."""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="package_dashboard"),
    path("customers/", views.package_list, name="package_list"),
    path("add/", views.package_add, name="package_add"),
    path("<int:pk>/", views.package_detail, name="package_detail"),
    path("<int:pk>/edit/", views.package_edit, name="package_edit"),
    path("<int:pk>/delete/", views.package_delete, name="package_delete"),
    path("<int:pk>/renew/", views.package_renew, name="package_renew"),
    path("<int:pk>/visits/add/", views.visit_add, name="package_visit_add"),
    path("<int:pk>/visits/<int:visit_id>/delete/", views.visit_delete, name="package_visit_delete"),
    path("<int:pk>/follow-up/", views.follow_up_update, name="package_follow_up"),
    path("follow-up/", views.follow_ups, name="package_follow_ups"),
    path("renewals/", views.renewal_history, name="package_renewals"),
    path("rates/", views.rates, name="package_rates"),
]

