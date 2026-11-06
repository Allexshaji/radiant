from django.urls import path
from . import my_reports, my_work, views

urlpatterns = [
    path("", views.dashboard, name="admin_dashboard"),
    path("staff/pending/", views.pending_staff, name="pending_staff_approval"),
    path("staff/<int:staff_id>/approve/", views.approve_staff, name="approve_staff"),
       # 1. Page to view all staff live status
    path('staff/attendance/', views.all_staff_attendance, name='all_staff_attendance'),
    
    # 2. Page to view a single staff member's history
    path('admin/staff/<int:staff_id>/attendance/', views.staff_attendance_history, name='staff_attendance_history'),
    path("admin/all_staffs/", views.all_staff, name="all_staff_reports_list"),
    path("admin/all_staffs_reports_view/", views.all_staff_reports_view, name="all_staff_reports_view"),
    path('report/view/walkins/<int:report_id>/', views.view_walkins, name='view_walkins'),
    path('report/view/revenues/<int:report_id>/', views.view_revenues, name='view_revenue'),
    path('report/view/payments/<int:report_id>/', views.view_payments, name='view_payments'),
    path('report/view/expenses/<int:report_id>/', views.view_expenses, name='view_expenses'),

    path("admin/staff/single/<int:staff_id>/reports/",views.single_staff_reports,name="single_staff_reports"),

    # An admin's own daily reports, with the same pages as the staff report pages
    path("my-reports/", my_reports.report_dashboard, name="admin_report_dashboard"),
    path("my-reports/add/", my_reports.reports_add, name="admin_reports_add"),
    path("my-reports/create/", my_reports.create_report, name="admin_create_report"),
    path("my-reports/<int:report_id>/", my_reports.report_hub, name="admin_report_hub"),
    path("my-reports/<int:report_id>/delete/", my_reports.delete_report, name="admin_delete_report"),
    path("my-reports/<int:report_id>/send/", my_reports.send_report, name="admin_send_report"),
    path("my-reports/<int:report_id>/walkins/", my_reports.add_walkins, name="admin_add_walkins"),
    path("my-reports/<int:report_id>/revenue/", my_reports.add_revenues, name="admin_add_revenues"),
    path("my-reports/<int:report_id>/expenses/", my_reports.add_expenses, name="admin_add_expenses"),
    path("my-reports/<int:report_id>/walkins/edit/", my_reports.edit_walkins, name="admin_edit_walkins"),
    path("my-reports/<int:report_id>/revenue/edit/", my_reports.edit_revenue, name="admin_edit_revenue"),
    path("my-reports/<int:report_id>/expenses/edit/", my_reports.edit_expenses, name="admin_edit_expenses"),
    path("my-reports/<int:report_id>/expenses/view/", my_reports.view_expense_report, name="admin_view_expense_report"),
    path("my-reports/<int:report_id>/expenses/delete/", my_reports.delete_expense_report, name="admin_delete_expense_report"),
    path("my-reports/history/", my_reports.reports_history, name="admin_reports_history"),
    path("my-reports/history/walkins/", my_reports.walkins_history_list, name="admin_walkins_history"),
    path("my-reports/history/revenue/", my_reports.revenue_history_list, name="admin_revenue_history"),
    path("my-reports/history/expenses/", my_reports.expenses_history_list, name="admin_expenses_history"),
    # An admin's own work (see admin_panel/my_work.py)
    path("my-work/attendance/", my_work.my_attendance, name="admin_my_attendance"),
    path("my-work/leave/", my_work.my_leave_dashboard, name="admin_my_leave"),
    path("my-work/leave/apply/", my_work.my_apply_leave, name="admin_my_apply_leave"),
    path("my-work/leave/<int:application_id>/", my_work.my_leave_detail, name="admin_my_leave_detail"),
    path("my-work/profile/", my_work.my_profile, name="admin_my_profile"),
    path("my-work/profile/edit/", my_work.my_profile_edit, name="admin_my_profile_edit"),
    path("my-work/salary/", my_work.my_salary, name="admin_my_salary"),

    path("report/<int:report_id>/approve/",views.approve_report,name="approve_report",),
    path("report/<int:report_id>/reject/",views.reject_report,name="reject_report",),
    path("report/<int:report_id>/edit/approval/",views.edit_approval,name="edit_approval",),
    path("branches/",views.branch_list,name="branch_list",),
    path("branches/create/", views.branch_create,name="branch_create",),
    path("branches/<int:branch_id>/edit/", views.branch_edit, name="branch_edit"),
    path("branches/<int:branch_id>/delete/", views.delete_branch_view, name="delete_branch"),
    path("admin/staff/", views.all_staff_view, name="all_staff"),
    path("admin/staff/<int:staff_id>/edit/", views.edit_staff_view, name="edit_staff"),
    path("admin/staff/<int:staff_id>/delete/", views.delete_staff_view, name="delete_staff"),
    path("admins/", views.all_admins_view, name="all_admins"),
    path("admins/add/", views.add_admin_view, name="add_admin"),
    path("admins/<int:admin_id>/delete/", views.delete_admin_view, name="delete_admin"),

    path('admin/leaves/', views.admin_leave_dashboard, name='admin_leave_dashboard'),
    path('admin/leaves/list/', views.admin_leave_list, name='admin_leave_list'),
    path('admin/leaves/<int:application_id>/review/', views.admin_review_leave, name='admin_review_leave'),
    path('leaves/edit/<int:leave_id>/', views.edit_leave, name='edit_leave'),
    path('leave-requests/', views.all_leave_requests, name='all_leave_requests'),
    path('leave-requests/approve/<int:pk>/', views.approve_leave, name='approve_leave'),
    path('leave-requests/reject/<int:pk>/', views.reject_leave, name='reject_leave'),
    path('leave-requests/delete/<int:pk>/', views.delete_leave_request, name='delete_leave_request'),

    path('leave-types/', views.leavetype_list, name='leavetype_list'),
    path('leave-types/create/', views.leavetype_create, name='leavetype_create'),
    path('leave-types/<int:leavetype_id>/edit/', views.leavetype_edit, name='leavetype_edit'),
    path('leave-types/<int:leavetype_id>/delete/', views.leavetype_delete, name='leavetype_delete'),

    path('expense-types/', views.expensetype_list, name='expensetype_list'),
    path('expense-types/create/', views.expensetype_create, name='expensetype_create'),
    path('expense-types/<int:expensetype_id>/edit/', views.expensetype_edit, name='expensetype_edit'),
    path('expense-types/<int:expensetype_id>/delete/', views.expensetype_delete, name='expensetype_delete'),

    path('requirements/', views.admin_requirements, name='admin_requirements'),
    path('requirements/<int:requirement_id>/approve/', views.admin_approve_requirement, name='admin_approve_requirement'),
     path('salary/manage/', views.admin_salary_manage, name='admin_salary_manage'),
    path('salary/allowance/<int:staff_id>/', views.admin_salary_allowance, name='admin_salary_allowance'),
    path('salary/add-staff/', views.admin_salary_add_staff, name='admin_salary_add_staff'),
    path('salary/<int:salary_id>/edit-staff/', views.admin_salary_edit_staff, name='admin_salary_edit_staff'),
    path('salary/<int:salary_id>/delete/', views.admin_salary_delete_staff, name='admin_salary_delete_staff'),
    path('salary/<int:salary_id>/detail/', views.admin_salary_detail, name='admin_salary_detail'),
    path('salary/rates/save/', views.admin_salary_save_rates, name='admin_salary_save_rates'),

]

