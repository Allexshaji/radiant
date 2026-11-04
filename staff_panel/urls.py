from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="staff_dashboard"),
    path("check-in/", views.check_in, name="check_in"),
    path("check-out/", views.check_out, name="check_out"),

    path('attendance/', views.attendance_page, name='attendance_page'),

    path('report/', views.report_dashboard, name='report_dashboard'),
    path("report/create/",views.create_report,name="create_report"),
    path("report/<int:report_id>/",views.report_hub,name="report_hub",),
    path("report/<int:report_id>/delete/",views.delete_report,name="delete_report",),
    path('report/history/walkins/<int:report_id>/edit/', views.edit_walkins_section, name='edit_walkins_section'),
    path('report/history/revenues/<int:report_id>/edit/', views.edit_revenue_section, name='edit_revenue_section'),
    path('report/history/payments/<int:report_id>/edit/', views.edit_payments_section, name='edit_payments_section'),
    path('report/history/expenses/<int:report_id>/edit/', views.edit_expenses_section, name='edit_expenses_section'),
    path("report/history/expenses/<int:report_id>/view/",views.view_expense_report,name="view_expense_report",),
    path("report/history/expenses/<int:report_id>/delete/",views.delete_expense_report,name="delete_expense_report",),

    path('report/add', views.reports_add, name='reports_add'),
    path("report/add/walkins/<int:report_id>/",views.add_walkins,name="add_walkins",),    
    path('report/add/revenues/<int:report_id>/', views.add_revenues, name='add_revenues'),
    path('report/add/payments/<int:report_id>/', views.add_payments, name='add_payments'),
    path('report/add/expenses/<int:report_id>/', views.add_expenses, name='add_expenses'),

    path('report/history', views.reports_history, name='reports_history'),
    path('report/history/walkins/', views.walkins_history_list, name='walkins_history_list'),
    path('report/history/revenue/', views.revenue_history_list, name='revenue_history_list'),
    path('report/history/payments/', views.payments_history_list, name='payments_history_list'),
    path('report/history/expenses/', views.expenses_history_list, name='expenses_history_list'),


    path("profile/", views.staff_profile, name="staff_profile"),
    path("salary/", views.staff_salary_management, name="staff_salary_management"),
    path("requirements/", views.staff_requirements, name="staff_requirements"),
    path("profile/edit/",views.edit_staff_profile,name="edit_staff_profile"),

    path('leaves/', views.staff_leave_dashboard, name='staff_leave_dashboard'),
    path('leaves/apply/', views.apply_leave, name='apply_leave'),
    path('leaves/<int:application_id>/', views.leave_application_detail, name='leave_detail'),
]

