from django.urls import path

from . import views

urlpatterns = [
    path("", views.super_dashboard, name="super_dashboard"),

    path("admins/", views.super_admin_list, name="super_admin_list"),
    path("admins/add/", views.super_admin_create, name="super_admin_create"),
    path("admins/<int:user_id>/edit/", views.super_admin_edit, name="super_admin_edit"),
    path("admins/<int:user_id>/toggle-active/", views.super_admin_toggle_active, name="super_admin_toggle_active"),
    path("admins/<int:user_id>/delete/", views.super_admin_delete, name="super_admin_delete"),

    path("staff-control/", views.staff_control, name="super_staff_control"),

    path("received-reports/", views.received_reports, name="super_received_reports"),
    path("received-reports/<int:submission_id>/review/", views.review_report, name="super_review_report"),
]
