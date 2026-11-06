"""Super Admin pages for the admins' own work: attendance, leave and salary.

An admin uses the My Work pages (admin_panel/my_work.py) for their own records.
The Super Admin sees the same records here. Admin leave is approved from this
inbox with the same approve and reject actions the leave pages use. The Super Admin
also sets each admin's monthly salary and allowance.
"""
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import User
from admin_panel.models import Salary
from admin_panel.payroll import monthly_summary
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
    """Each admin's pay for this month. Open an admin to see the history and set the monthly salary."""
    today = timezone.localdate()
    rows = [{"account": admin, "payroll": monthly_summary(admin, today)} for admin in _admins()]
    return render(request, "super_admin/admin_salary.html", {"rows": rows})


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
    """One admin's salary: this month's pay, the salary history, and the monthly salary and allowance."""
    account = get_object_or_404(User, pk=user_id, role=User.ADMIN)
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
