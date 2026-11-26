"""Super Admin pages for the admins' own work: attendance, leave and salary.

An admin uses the My Work pages (admin_panel/my_work.py) for their own records.
The Super Admin sees the same records here. Admin leave is approved from this
inbox with the same approve and reject actions the leave pages use. The Super Admin
also sets each admin's monthly salary and allowance.
"""
from decimal import Decimal, InvalidOperation

from urllib.parse import urlencode

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import Branch, User
from admin_panel.models import Salary
from admin_panel.payroll import monthly_summary, parse_month
from staff_panel.models import Attendance, LeaveApplication
from staff_panel.views import _approved_leave_on, attendance_context

from .views import super_admin_required

PERIODS = [("today", "Today"), ("week", "This week"), ("month", "This month"), ("all", "All time")]
LEAVE_STATUSES = ["pending", "approved", "rejected", "all"]


def _admins():
    return User.objects.filter(role=User.ADMIN).select_related("branch").order_by("branch__name", "username")


def _today_status(admin, today):
    """Label and colour for one admin's day: On leave, Working, Checked out or Absent."""
    if _approved_leave_on(admin, today) is not None:
        return "On leave", "bg-amber-100 text-amber-800"
    shift = Attendance.objects.filter(staff=admin, date=today).order_by("-check_in").first()
    if shift is None:
        return "Absent", "bg-red-100 text-red-800"
    if shift.check_out is None:
        return "Working", "bg-green-100 text-green-800"
    return "Checked out", "bg-gray-100 text-gray-800"


@super_admin_required
def admin_attendance(request):
    """Admin attendance. With no admin chosen: today's status for each admin. With one: that admin's history."""
    today = timezone.localdate()
    period = request.GET.get("filter", "month")
    if period not in dict(PERIODS):
        period = "month"

    admins = _admins()
    chosen = request.GET.get("admin", "")
    selected = admins.filter(pk=int(chosen)).first() if chosen.isdigit() else None

    context = {"admins": admins, "selected": selected, "periods": PERIODS, "period": period}
    if selected is not None:
        context.update(attendance_context(selected, period))
    else:
        rows = []
        for admin in admins:
            status, color = _today_status(admin, today)
            rows.append({"account": admin, "status": status, "color": color})
        context["rows"] = rows
    return render(request, "super_admin/admin_attendance.html", context)


@super_admin_required
def admin_leave(request):
    """Leave applied for by admins. Only a Super Admin decides on these."""
    status = request.GET.get("status", "pending")
    if status not in LEAVE_STATUSES:
        status = "pending"

    leaves = (
        LeaveApplication.objects.filter(staff__role=User.ADMIN)
        .select_related("staff", "staff__branch", "leave_type")
        .order_by("-applied_date")
    )
    if status != "all":
        leaves = leaves.filter(status=status)

    return render(request, "super_admin/admin_leave.html", {
        "leaves": leaves,
        "status": status,
        "statuses": LEAVE_STATUSES,
    })


@super_admin_required
def admin_salary(request):
    """The old Admin Salary page. Admins are now on Salary Management with staff, filtered to admins."""
    return redirect(f"{reverse('super_salary')}?role=admin")


ROLE_FILTERS = [("", "Staff & Admins"), ("staff", "Staff"), ("admin", "Admins")]


def _salary_url(request):
    """The Salary Management page with the filters the form came from, so a save or delete returns there."""
    query = {k: request.POST.get(k) for k in ("role", "branch", "q", "month") if request.POST.get(k)}
    url = reverse("super_salary")
    return f"{url}?{urlencode(query)}" if query else url


@super_admin_required
def salary_management(request):
    """Staff and admin salaries together, for one month. Filter by role, branch or name."""
    month = parse_month(request.GET.get("month")) or timezone.localdate().replace(day=1)
    role = request.GET.get("role", "")
    if role not in dict(ROLE_FILTERS):
        role = ""
    branch_id = request.GET.get("branch", "")
    branch = Branch.objects.filter(pk=int(branch_id)).first() if branch_id.isdigit() else None
    query = request.GET.get("q", "").strip()

    people = User.objects.filter(
        Q(role=User.ADMIN) | Q(role=User.STAFF, is_approved=True)
    ).select_related("branch")
    if role == "staff":
        people = people.filter(role=User.STAFF)
    elif role == "admin":
        people = people.filter(role=User.ADMIN)
    if branch:
        people = people.filter(branch=branch)
    if query:
        people = people.filter(
            Q(full_name__icontains=query) | Q(first_name__icontains=query)
            | Q(last_name__icontains=query) | Q(username__icontains=query)
        )
    people = people.annotate(records=Count("salaries")).order_by("role", "branch__name", "full_name", "username")

    rows = [{"account": person, "payroll": monthly_summary(person, month)} for person in people]
    set_rows = [r for r in rows if r["payroll"]["has_rate"]]
    return render(request, "super_admin/salary_management.html", {
        "rows": rows,
        "month": month,
        "role": role,
        "role_filters": ROLE_FILTERS,
        "branches": Branch.objects.order_by("name"),
        "selected_branch": branch,
        "query": query,
        "totals": {
            "people": len(rows),
            "staff": sum(1 for r in rows if r["account"].role == User.STAFF),
            "admins": sum(1 for r in rows if r["account"].role == User.ADMIN),
            "without_salary": len(rows) - len(set_rows),
            "monthly": sum((r["payroll"]["monthly"] for r in set_rows), Decimal("0")),
            "deduction": sum((r["payroll"]["deduction"] for r in set_rows), Decimal("0")),
            "allowance": sum((r["payroll"]["allowance"] for r in rows), Decimal("0")),
            "payable": sum((r["payroll"]["total"] for r in set_rows), Decimal("0")),
        },
    })


@super_admin_required
@require_POST
def salary_delete(request, user_id):
    """Delete all of one person's salary data: every salary record, the monthly salary and the allowance.

    The person's account, attendance and leave are kept. Only the salary data goes.
    """
    account = get_object_or_404(User, pk=user_id, role__in=[User.ADMIN, User.STAFF])
    name = account.full_name or account.username
    with transaction.atomic():
        records, _ = Salary.objects.filter(staff=account).delete()
        account.monthly_salary = None
        account.allowance = None
        account.save(update_fields=["monthly_salary", "allowance"])
    messages.success(
        request,
        f"All salary data of {name} deleted ({records} salary record{'s' if records != 1 else ''}, "
        f"monthly salary and allowance).",
    )
    return redirect(_salary_url(request))


def _money(raw, label):
    """A money amount typed into a form. Blank means no amount. Returns (amount, error)."""
    if raw == "":
        return None, None
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        return None, f"{label}: enter the amount as a number."
    if not amount.is_finite():
        return None, f"{label}: enter the amount as a number."
    if amount < 0:
        return None, f"{label}: the amount cannot be negative."
    return amount.quantize(Decimal("0.01")), None


@super_admin_required
def admin_salary_detail(request, user_id):
    """One admin's or staff member's salary: this month's pay, the history, and the monthly salary and allowance."""
    account = get_object_or_404(User, pk=user_id, role__in=[User.ADMIN, User.STAFF])
    monthly_value = account.monthly_salary
    allowance_value = account.allowance

    if request.method == "POST":
        monthly_raw = request.POST.get("monthly_salary", "").strip()
        allowance_raw = request.POST.get("allowance", "").strip()
        monthly_value, allowance_value = monthly_raw, allowance_raw

        monthly, error = _money(monthly_raw, "Monthly salary")
        allowance, allowance_error = _money(allowance_raw, "Allowance")
        error = error or allowance_error
        if error is None and monthly is None:
            error = "Monthly salary: enter the amount."

        if error:
            messages.error(request, error)
        else:
            account.monthly_salary = monthly
            account.allowance = allowance
            account.save(update_fields=["monthly_salary", "allowance"])
            messages.success(request, f"Salary for {account.full_name or account.username} was saved.")
            return redirect("super_admin_admin_salary_detail", user_id=account.pk)

    return render(request, "super_admin/admin_salary_detail.html", {
        "account": account,
        "payroll": monthly_summary(account, timezone.localdate()),
        "salary_history": Salary.objects.filter(staff=account).order_by("-month")[:12],
        "monthly_value": monthly_value,
        "allowance_value": allowance_value,
    })
