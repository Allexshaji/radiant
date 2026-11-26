"""Massage package pages. Included under /admin/packages/, so only Admins and the Super Admin reach them."""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="package_dashboard"),
    path("customers/", views.customer_list, name="customer_list"),
    path("customers/new/", views.customer_add, name="customer_add"),
    path("customers/<int:pk>/", views.customer_detail, name="customer_detail"),
    path("customers/<int:pk>/edit/", views.customer_edit, name="customer_edit"),
    path("customers/<int:pk>/add-package/", views.customer_package_add, name="customer_package_add"),
    path("all/", views.package_list, name="package_list"),
    path("add/", views.package_add, name="package_add"),
    path("<int:pk>/", views.package_detail, name="package_detail"),
    path("<int:pk>/edit/", views.package_edit, name="package_edit"),
    path("<int:pk>/delete/", views.package_delete, name="package_delete"),
    path("<int:pk>/renew/", views.package_renew, name="package_renew"),
    path("<int:pk>/visits/add/", views.visit_add, name="package_visit_add"),
    path("<int:pk>/visits/undo/", views.visit_undo, name="package_visit_undo"),
    path("<int:pk>/visits/<int:visit_id>/delete/", views.visit_delete, name="package_visit_delete"),
    path("<int:pk>/follow-up/", views.follow_up_update, name="package_follow_up"),
    path("follow-up/", views.follow_ups, name="package_follow_ups"),
    path("alerts/", views.alerts, name="package_alerts"),
    path("<int:pk>/called/", views.mark_called, name="package_mark_called"),
    path("renewals/", views.renewal_history, name="package_renewals"),
    path("rates/", views.rates, name="package_rates"),
]

