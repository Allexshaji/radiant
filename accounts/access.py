"""Who may open which page.

The middleware, the views and the templates all read the rules from here, so
a rule is written once.
"""
from django.urls import reverse

from .models import Branch, StaffFeatureSetting, User

ADMIN_ROLES = (User.SUPER_ADMIN, User.ADMIN)

# Parts of the admin module that a Super Admin can switch off for one admin.
# Each entry: (key, label, what it covers)
ADMIN_SECTIONS = [
    ("staff", "Staff", "Pending approvals, all staff, edit and remove staff"),
    ("attendance", "Attendance", "Staff attendance and attendance history"),
    ("reports", "Reports", "Staff reports, approvals, report views, and the admin's own daily reports"),
    ("requirements", "Requirements", "Requirements sent by staff"),
    ("leave", "Leave", "Leave dashboard, leave requests and leave policies"),
    ("expenses", "Expenses", "Expense names that staff choose from"),
    ("salary", "Salary", "Salary management"),
    ("branches", "Branches", "Add and manage branches"),
    ("admins", "Admins", "View the list of admin accounts. Only a Super Admin can add or remove admins"),
]

# Features of the staff module that a Super Admin can switch on or off for every staff member.
STAFF_FEATURES = [
    ("attendance", "Attendance", "Check in and check out"),
    ("reports", "Daily reports", "Create, edit and view daily reports"),
    ("leave", "Leave", "Apply for leave and see leave status"),
    ("requirements", "Requirements", "Send requirements to the admin"),
    ("salary", "Salary", "View salary details"),
]

# Admin page (URL name) -> admin section. Pages not listed here, such as the
# dashboard, are open to every admin.
ADMIN_URL_SECTIONS = {
    "pending_staff_approval": "staff",
    "approve_staff": "staff",
    "all_staff": "staff",
    "edit_staff": "staff",
    "delete_staff": "staff",

    "all_staff_attendance": "attendance",
    "staff_attendance_history": "attendance",

    "all_staff_reports_list": "reports",
    "all_staff_reports_view": "reports",
    "single_staff_reports": "reports",
    "view_walkins": "reports",
    "view_revenue": "reports",
    "view_payments": "reports",
    "view_expenses": "reports",
    "approve_report": "reports",
    "reject_report": "reports",
    "edit_approval": "reports",

    # An admin's own daily reports (see admin_panel/my_reports.py)
    "admin_report_dashboard": "reports",
    "admin_reports_add": "reports",
    "admin_create_report": "reports",
    "admin_report_hub": "reports",
    "admin_delete_report": "reports",
    "admin_send_report": "reports",
    "admin_add_walkins": "reports",
    "admin_add_revenues": "reports",
    "admin_add_expenses": "reports",
    "admin_edit_walkins": "reports",
    "admin_edit_revenue": "reports",
    "admin_edit_expenses": "reports",
    "admin_reports_history": "reports",
    "admin_walkins_history": "reports",
    "admin_revenue_history": "reports",
    "admin_expenses_history": "reports",
    "admin_view_expense_report": "reports",
    "admin_delete_expense_report": "reports",

    "admin_requirements": "requirements",
    "admin_approve_requirement": "requirements",

    "admin_leave_dashboard": "leave",
    "admin_leave_list": "leave",
    "admin_review_leave": "leave",
    "edit_leave": "leave",
    "all_leave_requests": "leave",
    "approve_leave": "leave",
    "reject_leave": "leave",
    "delete_leave_request": "leave",
    "leavetype_list": "leave",
    "leavetype_create": "leave",
    "leavetype_edit": "leave",
    "leavetype_delete": "leave",

    "expensetype_list": "expenses",
    "expensetype_create": "expenses",
    "expensetype_edit": "expenses",
    "expensetype_delete": "expenses",

    "admin_salary_manage": "salary",
    "admin_salary_allowance": "salary",
    "admin_salary_add_staff": "salary",
    "admin_salary_edit_staff": "salary",
    "admin_salary_delete_staff": "salary",
    "admin_salary_detail": "salary",
    "admin_salary_save_rates": "salary",

    "branch_list": "branches",
    "branch_create": "branches",
    "delete_branch": "branches",

    "all_admins": "admins",
    "add_admin": "admins",
    "delete_admin": "admins",
}

# Staff page (URL name) -> staff feature. Profile and dashboard are always open.
STAFF_URL_FEATURES = {
    "check_in": "attendance",
    "check_out": "attendance",
    "attendance_page": "attendance",

    "report_dashboard": "reports",
    "create_report": "reports",
    "report_hub": "reports",
    "delete_report": "reports",
    "edit_walkins_section": "reports",
    "edit_revenue_section": "reports",
    "edit_payments_section": "reports",
    "edit_expenses_section": "reports",
    "view_expense_report": "reports",
    "delete_expense_report": "reports",
    "reports_add": "reports",
    "add_walkins": "reports",
    "add_revenues": "reports",
    "add_payments": "reports",
    "add_expenses": "reports",
    "reports_history": "reports",
    "walkins_history_list": "reports",
    "revenue_history_list": "reports",
    "payments_history_list": "reports",
    "expenses_history_list": "reports",

    "staff_leave_dashboard": "leave",
    "apply_leave": "leave",
    "leave_detail": "leave",

    "staff_requirements": "requirements",

    "staff_salary_management": "salary",
}


def branches_for(user):
    """Branches this user may see or choose: all of them for a Super Admin, only their own for an Admin."""
    if getattr(user, "role", None) == User.SUPER_ADMIN:
        return Branch.objects.all()
    if getattr(user, "role", None) == User.ADMIN and user.branch_id:
        return Branch.objects.filter(pk=user.branch_id)
    return Branch.objects.none()


def in_my_branch(queryset, user, path=""):
    """Keep only the rows this user may see, by branch.

    A Super Admin sees everything. An Admin sees only rows of staff in their own branch.
    `path` is the lookup from each row to its staff member ("staff" for reports, leave,
    requirements and salary), or "" when the queryset holds the staff accounts themselves.
    An Admin with no branch sees nothing.
    """
    if getattr(user, "role", None) == User.SUPER_ADMIN:
        return queryset
    if getattr(user, "role", None) != User.ADMIN or not user.branch_id:
        return queryset.none()
    field = f"{path}__branch_id" if path else "branch_id"
    return queryset.filter(**{field: user.branch_id})


def is_admin_role(user):
    """True for Admins and Super Admins. Used where both may act."""
    return getattr(user, "role", None) in ADMIN_ROLES


def is_super_admin(user):
    return getattr(user, "role", None) == User.SUPER_ADMIN


def home_url_for(user):
    """Where a user lands after signing in."""
    if user.role == User.SUPER_ADMIN:
        return reverse("super_dashboard")
    if user.role == User.ADMIN:
        return reverse("admin_dashboard")
    return reverse("staff_dashboard")


def admin_section_for(url_name):
    return ADMIN_URL_SECTIONS.get(url_name)


def staff_feature_for(url_name):
    return STAFF_URL_FEATURES.get(url_name)


def staff_feature_enabled(key):
    enabled = StaffFeatureSetting.objects.filter(key=key).values_list("is_enabled", flat=True).first()
    return True if enabled is None else enabled


def staff_feature_states():
    saved = dict(StaffFeatureSetting.objects.values_list("key", "is_enabled"))
    return {key: saved.get(key, True) for key, _label, _text in STAFF_FEATURES}


class Permissions:
    """What the signed-in user may open. Templates read it as {{ can.leave }}."""

    KEYS = {
        "staff", "attendance", "reports", "requirements", "leave",
        "expenses", "salary", "branches", "admins", "super_admin",
    }

    def __init__(self, user):
        self.user = user
        self._features = None

    def __getattr__(self, key):
        if key not in self.KEYS:
            raise AttributeError(key)
        return self._allowed(key)

    def _allowed(self, key):
        role = self.user.role
        if role == User.SUPER_ADMIN:
            return True
        if key == "super_admin":
            return False
        if role == User.ADMIN:
            return key not in (self.user.blocked_sections or [])
        if role == User.STAFF:
            if self._features is None:
                self._features = staff_feature_states()
            return self._features.get(key, True)
        return False
