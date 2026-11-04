"""The admin sidebar, described as data so every admin and super admin page builds it the same way.

Each item: (section, label, icon, url name, url names that light it up).
A section of None is always shown. Otherwise the item is shown only when
the user's permissions allow that section (see accounts.access).
"""
from django.urls import reverse

NAV_GROUPS = [  # (heading, items)
    (None, [
        (None, "Dashboard", "fa-solid fa-chart-pie", "admin_dashboard", ["admin_dashboard"]),
    ]),
    ("Super Admin", [
        ("super_admin", "Super Dashboard", "fa-solid fa-crown", "super_dashboard", ["super_dashboard"]),
        ("super_admin", "Admin Accounts", "fa-solid fa-user-gear", "super_admin_list",
         ["super_admin_list", "super_admin_edit"]),
        ("super_admin", "Add Admin", "fa-solid fa-user-plus", "super_admin_create", ["super_admin_create"]),
        ("super_admin", "Add Branch", "fa-solid fa-plus", "branch_create", ["branch_create"]),
        ("super_admin", "Staff Control", "fa-solid fa-sliders", "super_staff_control", ["super_staff_control"]),
    ]),
    ("Staff", [
        ("staff", "Pending Approvals", "fa-solid fa-user-clock", "pending_staff_approval",
         ["pending_staff_approval", "approve_staff"]),
        ("staff", "All Staff", "fa-solid fa-users", "all_staff", ["all_staff", "edit_staff", "delete_staff"]),
        ("attendance", "Staff Attendance", "fa-solid fa-calendar-check", "all_staff_attendance",
         ["all_staff_attendance", "staff_attendance_history"]),
        ("reports", "All Staff Reports", "fa-solid fa-file-invoice", "all_staff_reports_list",
         ["all_staff_reports_list", "view_revenue", "view_payments", "view_expenses", "view_walkins"]),
        ("reports", "Staff Reports View", "fa-solid fa-chart-column", "all_staff_reports_view",
         ["all_staff_reports_view", "single_staff_reports"]),
        ("requirements", "Requirements", "fa-solid fa-clipboard-list", "admin_requirements",
         ["admin_requirements", "admin_approve_requirement"]),
    ]),
    ("Leave", [
        ("leave", "Leave Dashboard", "fa-solid fa-calendar-days", "admin_leave_dashboard",
         ["admin_leave_dashboard", "admin_review_leave"]),
        ("leave", "Leave Requests", "fa-solid fa-envelope-open-text", "all_leave_requests", ["all_leave_requests"]),
        ("leave", "Leave Policies", "fa-solid fa-tags", "leavetype_list",
         ["leavetype_list", "leavetype_create", "leavetype_edit", "leavetype_delete"]),
    ]),
    ("Finance", [
        ("salary", "Salary Management", "fa-solid fa-money-bill-wave", "admin_salary_manage",
         ["admin_salary_manage", "admin_salary_add_staff", "admin_salary_edit_staff",
          "admin_salary_delete_staff", "admin_salary_allowance", "admin_salary_detail",
          "admin_salary_save_rates"]),
        ("expenses", "Expenses", "fa-solid fa-receipt", "expensetype_list",
         ["expensetype_list", "expensetype_create", "expensetype_edit", "expensetype_delete"]),
    ]),
    ("Organisation", [
        ("branches", "Branches", "fa-solid fa-code-branch", "branch_list", ["branch_list", "delete_branch"]),
    ]),
    ("Admins", [
        ("admins", "All Admins", "fa-solid fa-user-shield", "all_admins", ["all_admins", "delete_admin"]),
    ]),
]


def build_admin_nav(can):
    """Return the groups and items this user may see, with their URLs filled in."""
    groups = []
    for heading, items in NAV_GROUPS:
        visible = []
        for section, label, icon, url_name, highlight in items:
            if section is None or getattr(can, section):
                visible.append({
                    "label": label,
                    "icon": icon,
                    "url": reverse(url_name),
                    "highlight": highlight,
                })
        if visible:
            groups.append({"heading": heading, "items": visible})
    return groups
