"""An admin's own work: attendance, leave, profile and salary.

These are the pages a staff member has on the staff side, for the admin's own records.
The check-in rules and the attendance history are the same code the staff pages use,
so both groups get the same results. Only the owner changes: an admin sees and changes
only their own records. Pages can be switched off per admin by a Super Admin
(see accounts/access.py, ADMIN_SECTIONS).

A Super Admin reviews admin leave and sees admin attendance and salary in the
Admin Work pages (super_admin/views.py).
"""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import User
from admin_panel.models import LeaveType, Salary
from admin_panel.payroll import monthly_summary
from staff_panel.forms import LeaveApplicationForm
from staff_panel.models import LeaveApplication
from staff_panel.views import _flash_check_result, attendance_context


def my_work_required(view):
    """Only an Admin reaches these pages. A Super Admin and staff are turned away."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if getattr(request.user, "role", None) != User.ADMIN:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return login_required(wrapper)


@my_work_required
def my_attendance(request):
    """My Attendance: check in and check out, and see my own attendance and leave history."""
    user = request.user

    # Check-in and check-out are sent as a normal form POST, then the page reloads with a message.
    if request.method == "POST":
        action = request.POST.get("action")
        if action in ("check_in", "check_out"):
            _flash_check_result(request, action)
        else:
            messages.error(request, "Invalid action.")
        return redirect("admin_my_attendance")

    if user.branch_id is None:
        messages.error(request, "Your account does not have a branch assigned.")
        return redirect("admin_dashboard")

    context = attendance_context(user, request.GET.get("filter", "month"))
    return render(request, "admin_panel/my_work/attendance.html", context)


@my_work_required
def my_leave_dashboard(request):
    """My Leave: my own leave applications and their status. A Super Admin approves them."""
    leaves = LeaveApplication.objects.filter(staff=request.user)
    context = {
        "pending_leaves": leaves.filter(status="pending"),
        "approved_leaves": leaves.filter(status="approved"),
        "rejected_leaves": leaves.filter(status="rejected"),
        "total_pending": leaves.filter(status="pending").count(),
        "total_approved": leaves.filter(status="approved").count(),
    }
    return render(request, "admin_panel/my_work/leave_dashboard.html", context)


@my_work_required
def my_apply_leave(request):
    """Apply for my own leave."""
    if request.method == "POST":
        form = LeaveApplicationForm(request.POST)
        if form.is_valid():
            application = form.save(commit=False)
            application.staff = request.user
            application.save()
            messages.success(request, "Leave application submitted successfully! ✓")
            return redirect("admin_my_leave")
        messages.error(request, "Please correct the errors below")
    else:
        form = LeaveApplicationForm()

    context = {
        "form": form,
        "leave_types": LeaveType.objects.filter(is_active=True),
    }
    return render(request, "admin_panel/my_work/apply_leave.html", context)


@my_work_required
def my_leave_detail(request, application_id):
    """One of my own leave applications. Anyone else's is not found here."""
    application = get_object_or_404(LeaveApplication, id=application_id, staff=request.user)
    return render(request, "admin_panel/my_work/leave_detail.html", {"application": application})


@my_work_required
def my_profile(request):
    """My Profile: my account details."""
    return render(request, "admin_panel/my_work/profile.html", {"user": request.user})


def _profile_problem(user, first_name, username, email):
    """The first problem with the profile details, or None when they can be saved."""
    if not first_name:
        return "Name is required."
    if not username:
        return "Username is required."
    if not email:
        return "Email is required."
    if User.objects.filter(username=username).exclude(id=user.id).exists():
        return "This username is already in use."
    if User.objects.filter(email=email).exclude(id=user.id).exists():
        return "This email address is already in use."
    return None


@my_work_required
def my_profile_edit(request):
    """Change my name, username and email. Same rules as the staff profile page."""
    user = request.user

    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()

        problem = _profile_problem(user, first_name, username, email)
        if problem:
            messages.error(request, problem)
            return redirect("admin_my_profile_edit")

        user.first_name = first_name
        user.last_name = last_name
        user.username = username
        user.email = email
        user.save()

        messages.success(request, "Profile updated successfully.")
        return redirect("admin_my_profile")

    return render(request, "admin_panel/my_work/edit_profile.html", {"user": user})


@my_work_required
def my_salary(request):
    """My Salary: this month's pay and my last six salary records."""
    payroll = monthly_summary(request.user, timezone.localdate())
    context = {
        "payroll": payroll,
        "salary_history": Salary.objects.filter(staff=request.user).order_by("-month")[:6],
    }
    return render(request, "admin_panel/my_work/salary.html", context)
