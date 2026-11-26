from django.urls import path

from . import admin_work, report_review, views

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

    # The Super Admin's own branch reports: pick a branch and a date, then fill the report
    path("reports/", views.super_reports, name="super_reports"),
    path("reports/create/", views.super_report_create, name="super_report_create"),

    path("staff-access/", views.staff_access, name="super_staff_access"),
    path("staff-access/<int:user_id>/", views.staff_access_edit, name="super_staff_access_edit"),

    # Admin work: an admin's attendance, leave and salary (see super_admin/admin_work.py)
    path("admin-attendance/", admin_work.admin_attendance, name="super_admin_attendance"),
    path("admin-leave/", admin_work.admin_leave, name="super_admin_admin_leave"),
    path("admin-salary/", admin_work.admin_salary, name="super_admin_admin_salary"),
    path("admin-salary/<int:user_id>/", admin_work.admin_salary_detail, name="super_admin_admin_salary_detail"),

    # Salary Management: staff and admin salaries together, in Finance (see super_admin/admin_work.py)
    path("salary/", admin_work.salary_management, name="super_salary"),
    path("salary/<int:user_id>/delete/", admin_work.salary_delete, name="super_salary_delete"),

    # Review admin and staff reports: choose a person, then edit, approve or reject (see report_review.py)
    path("admin-reports/", report_review.review_reports, {"kind": "admin"}, name="super_admin_reports"),
    path("staff-reports/", report_review.review_reports, {"kind": "staff"}, name="super_staff_reports"),
    path("review-reports/<int:report_id>/status/", report_review.set_report_status, name="super_set_report_status"),
    path("review-reports/<int:report_id>/delete/", report_review.delete_report, name="super_delete_report"),
]
