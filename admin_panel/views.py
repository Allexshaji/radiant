from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth.password_validation import validate_password
from django.shortcuts import render,get_object_or_404, redirect
from django.contrib.auth.hashers import make_password


from accounts.models import User
from accounts.forms import StaffRegistrationForm
from .forms import StaffApprovalForm,BranchForm
from django.db.models import Q
from django.contrib import messages


from django.utils import timezone
from django.contrib.auth import get_user_model
from staff_panel.models import Attendance 
from staff_panel.models import (
    DailyReport,
    WalkInService,
    Revenue,
    PaymentSummary,
    ExpenseItem,
    Attendance
)


from staff_panel.models import DailyReport
from django.core.paginator import Paginator



from django.shortcuts import render
from django.db.models import OuterRef, Subquery
from staff_panel.forms import (
    WalkinServicesForm,
    RevenueBreakdownForm,
    PaymentSummaryForm,
    ExpenseItemForm,
    ExpenseFormSet,
)
from accounts.models import Branch

User = get_user_model()
from decimal import Decimal


from decimal import Decimal

from django.contrib.auth.decorators import login_required,user_passes_test
from django.core.exceptions import PermissionDenied

from accounts.models import User
from staff_panel.models import DailyReport
from staff_panel.models import LeaveApplication
from staff_panel.forms import LeaveApprovalForm
from django.db.models import ProtectedError
from admin_panel.models import LeaveType, ExpenseType
from staff_panel.models import Requirement
from admin_panel.forms import LeaveTypeForm, ExpenseTypeForm
from admin_panel.payroll import parse_month, staff_payroll_rows
from accounts.access import branches_for, in_my_branch, is_admin_role, is_super_admin

@login_required
def dashboard(request):
    if not is_admin_role(request.user):
        raise PermissionDenied

    reports = in_my_branch(DailyReport.objects.all(), request.user, "staff")

    total_revenue = sum(
        (report.total_revenue or Decimal("0.00"))
        for report in reports
    )

    total_expenses = sum(
        (report.total_expenses or Decimal("0.00"))
        for report in reports
    )

    total_payments = sum(
        (report.total_payments or Decimal("0.00"))
        for report in reports
    )

    total_walkins = sum(
        (report.total_walkins or 0)
        for report in reports
    )

    net_amount = total_revenue - total_expenses

    pending_count = in_my_branch(User.objects.filter(role=User.STAFF, is_approved=False), request.user).count()
    staff_count = in_my_branch(User.objects.filter(role=User.STAFF, is_approved=True), request.user).count()
    admin_count = in_my_branch(User.objects.filter(role=User.ADMIN), request.user).count()
    branch_count = branches_for(request.user).count()

    context = {
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "total_payments": total_payments,
        "total_walkins": total_walkins,
        "net_amount": net_amount,
        "pending_count": pending_count,
        "staff_count": staff_count,
        "admin_count": admin_count,
        "branch_count": branch_count,
    }

    return render(
        request,
        "admin_panel/dashboard.html",
        context
    )



@login_required
def pending_staff(request):
    if not is_admin_role(request.user):
        raise PermissionDenied

    staff_members = in_my_branch(User.objects.filter(
        role=User.STAFF,
        is_approved=False,
    ), request.user)

    return render(
        request,
        "admin_panel/pending_staff.html",
        {"staff_members": staff_members},
    )


@login_required
def approve_staff(request, staff_id):
    if not is_admin_role(request.user):
        raise PermissionDenied

    staff = get_object_or_404(
        in_my_branch(User.objects.all(), request.user),
        id=staff_id,
        role=User.STAFF,
        is_approved=False,
    )

    if request.method == "POST":
        form = StaffApprovalForm(request.POST, instance=staff)
        form.fields["branch"].queryset = branches_for(request.user)

        if form.is_valid():
            approved_staff = form.save(commit=False)
            approved_staff.is_approved = True
            approved_staff.save()
            form.save_m2m()
            return redirect("pending_staff_approval")
    else:
        form = StaffApprovalForm(instance=staff)
        form.fields["branch"].queryset = branches_for(request.user)

    return render(
        request,
        "admin_panel/approve_staff.html",
        {"form": form, "staff": staff},
    )


@login_required
def all_staff_attendance(request):
    if not is_admin_role(request.user):
        raise PermissionDenied

    today = timezone.localdate()
    staff_members = in_my_branch(User.objects.filter(role=User.STAFF, is_approved=True), request.user)
    
    live_attendance = []
    for staff in staff_members:
        latest_shift = Attendance.objects.filter(staff=staff, date=today).order_by('-check_in').first()
        
        if not latest_shift:
            status, color = "Absent", "bg-red-100 text-red-800"
        elif not latest_shift.check_out:
            status, color = "Working", "bg-green-100 text-green-800"
        else:
            status, color = "Checked Out", "bg-gray-100 text-gray-800"
            
        live_attendance.append({
            'staff': staff,
            'status': status,
            'color': color,
            'shift': latest_shift
        })

    # Leave Approval and Leave Management boxes, from real leave records.
    pending = reviewable_leaves(request.user).filter(status='pending').select_related('staff', 'leave_type').order_by('applied_date')
    pending_count = pending.count()
    pending_staff_count = pending.order_by().values('staff').distinct().count()
    on_leave_today = reviewable_leaves(request.user).filter(status='approved', start_date__lte=today, end_date__gte=today).count()
    upcoming_leaves = reviewable_leaves(request.user).filter(status='approved', start_date__gt=today).count()

    return render(request, "admin_panel/all_staff_attendance.html", {
        "live_attendance": live_attendance,
        "pending_leaves": pending[:5],
        "pending_count": pending_count,
        "pending_staff_count": pending_staff_count,
        "on_leave_today": on_leave_today,
        "upcoming_leaves": upcoming_leaves,
    })

@login_required
def staff_attendance_history(request, staff_id):
    if not is_admin_role(request.user):
        raise PermissionDenied

    # Get the specific staff member
    staff = get_object_or_404(in_my_branch(User.objects.all(), request.user), id=staff_id, role=User.STAFF)
    
    # Get their entire history, newest first
    history = Attendance.objects.filter(staff=staff).prefetch_related('activities').order_by('-date', '-check_in')

    return render(request, "admin_panel/staff_attendance_history.html", {
        "staff": staff,
        "history": history
    })



def all_staff(request):

    latest_report = DailyReport.objects.filter(
        staff=OuterRef("staff")
    ).order_by("-report_date", "-id")

    reports = in_my_branch(DailyReport.objects.filter(
        id=Subquery(
            latest_report.values("id")[:1]
        )
    ), request.user, "staff").select_related(
        "staff",
        "branch"
    ).order_by(
        "-report_date"
    )

    submitted_count = reports.filter(
        status="SUBMITTED"
    ).count()

    approved_count = reports.filter(
        status="APPROVED"
    ).count()

    context = {
        "reports": reports,
        "submitted_count": submitted_count,
        "approved_count": approved_count,
    }

    return render(
        request,
        "admin_panel/reports/reports.html",
        context
    )






from datetime import datetime

from django.contrib.auth import get_user_model
from django.db.models import Exists, OuterRef, Subquery
from django.shortcuts import render
from django.utils import timezone


User = get_user_model()


def all_staff_reports_view(request):

    # Date filter: ?date=2026-09-26, defaults to today
    date_str = request.GET.get("date")
    try:
        selected_date = (
            datetime.strptime(date_str, "%Y-%m-%d").date()
            if date_str else timezone.localdate()
        )
    except ValueError:
        selected_date = timezone.localdate()

    day_report = DailyReport.objects.filter(
        staff=OuterRef("pk"),
        report_date=selected_date,
    ).order_by("-id")

    latest_report = DailyReport.objects.filter(
        staff=OuterRef("pk")
    ).order_by("-report_date", "-id")

    staff_list = (
        in_my_branch(User.objects.filter(is_active=True, role="STAFF"), request.user)
        .annotate(
            has_submitted=Exists(day_report),
            day_report_id=Subquery(day_report.values("id")[:1]),
            day_report_status=Subquery(day_report.values("status")[:1]),
            day_report_branch=Subquery(day_report.values("branch__name")[:1]),
            last_report_date=Subquery(latest_report.values("report_date")[:1]),
            last_report_branch=Subquery(latest_report.values("branch__name")[:1]),
        )
        .order_by("has_submitted", "first_name", "username")   # not-submitted first
    )

    total_staff = staff_list.count()
    submitted_count = staff_list.filter(has_submitted=True).count()
    not_submitted_count = total_staff - submitted_count
    approved_count = staff_list.filter(day_report_status="APPROVED").count()

    context = {
        "staff_list": staff_list,
        "selected_date": selected_date,
        "is_today": selected_date == timezone.localdate(),
        "total_staff": total_staff,
        "submitted_count": submitted_count,
        "not_submitted_count": not_submitted_count,
        "approved_count": approved_count,
    }

    return render(request, "admin_panel/reports/all_staff_reports_view.html", context)

def single_staff_reports(request, staff_id):

    staff = get_object_or_404(in_my_branch(User.objects.all(), request.user), id=staff_id)

    reports = DailyReport.objects.filter(
        staff=staff
    ).select_related(
        "branch"
    ).order_by(
        "-report_date",
        "-id"
    )

    return render(
        request,
        "admin_panel/reports/single_staff_reports.html",
        {
            "staff": staff,
            "reports": reports,
        }
    )









@login_required
def view_walkins(request, report_id):
    from decimal import Decimal


    report = get_object_or_404(
        in_my_branch(DailyReport.objects.select_related(
            "staff",
            "branch",
        ), request.user, "staff"),
        id=report_id
    )

    walkin, created = WalkInService.objects.get_or_create(
        report=report
    )

    # The payments for this day are shown on the same page as the walk-ins.
    payment = PaymentSummary.objects.filter(report=report).first()
    payment_total = payment.total_payments if payment else Decimal("0.00")

    return render(
        request,
        "admin_panel/reports/view_walkins.html",
        {
            "report": report,
            "walkin": walkin,
            "payment": payment,
            "payment_total": payment_total,
        }
    )

@login_required
def view_revenues(request, report_id):

    report = get_object_or_404(
        in_my_branch(DailyReport.objects.select_related(
            "staff",
            "branch",
        ), request.user, "staff"),
        id=report_id
    )

    revenue, created = Revenue.objects.get_or_create(
        report=report
    )

    return render(
        request,
        "admin_panel/reports/view_revenue.html",
        {
            "report": report,
            "revenue": revenue,
        }
    )
    

@login_required
def view_payments(request, report_id):
    """Payments are shown with the walk-ins, so this opens the walk-ins report."""
    return redirect("view_walkins", report_id=report_id)


@login_required
def view_expenses(request, report_id):

    report = get_object_or_404(
        in_my_branch(DailyReport.objects.select_related(
            "staff",
            "branch",
        ).prefetch_related(
            "expenses",
        ), request.user, "staff"),
        id=report_id
    )

    expenses = report.expenses.all()

    return render(
        request,
        "admin_panel/reports/view_expenses.html",
        {
            "report": report,
            "expenses": expenses,
        }
    )

@login_required
def approve_report(request, report_id):

    if not is_admin_role(request.user):
        messages.error(
            request,
            "Only administrators can approve reports."
        )
        return redirect("view_revenue", report_id=report_id)

    report = get_object_or_404(
        in_my_branch(DailyReport.objects.all(), request.user, "staff"),
        id=report_id
    )

    if request.method == "POST":

        report.status = DailyReport.APPROVED
        report.save()

        messages.success(
            request,
            "Report approved successfully!"
        )

    return redirect(
        "view_revenue",
        report_id=report.id
    )
@login_required
def reject_report(request, report_id):

    if not is_admin_role(request.user):
        messages.error(
            request,
            "Only administrators can reject reports."
        )

        return redirect(
            "view_revenue",
            report_id=report_id
        )

    report = get_object_or_404(
        in_my_branch(DailyReport.objects.all(), request.user, "staff"),
        id=report_id
    )

    if request.method == "POST":

        report.status = DailyReport.REJECTED
        report.save()

        messages.success(
            request,
            "Report rejected successfully!"
        )

    return redirect(
        "view_revenue",
        report_id=report.id
    )

@login_required
def edit_approval(request, report_id):

    if not is_admin_role(request.user):
        messages.error(
            request,
            "Only administrators can approve or reject reports."
        )
        return redirect("view_revenue", report_id=report_id)

    report = get_object_or_404(
        in_my_branch(DailyReport.objects.select_related(
            "staff",
            "branch",
        ), request.user, "staff"),
        id=report_id
    )

    next_page = request.GET.get("next", "view_revenue")

    if request.method == "POST":

        action = request.POST.get("action")

        if action == "approve":

            report.status = DailyReport.APPROVED
            report.save()

            messages.success(
                request,
                "Report approved successfully!"
            )

        elif action == "reject":

            report.status = DailyReport.REJECTED
            report.save()

            messages.success(
                request,
                "Report rejected successfully!"
            )

        return redirect(
            next_page,
            report_id=report.id
        )

    return render(
        request,
        "admin_panel/reports/edit_approval.html",
        {
            "report": report,
        }
    )


@login_required
def branch_list(request):

    if not is_admin_role(request.user):
        return redirect("admin_dashboard")

    # Every admin can see every branch. Only a Super Admin can change them.
    branches = Branch.objects.all().order_by("name")

    return render(
        request,
        "admin_panel/branches/branch_list.html",
        {
            "branches": branches,
        }
    )

@login_required
def branch_create(request):

    if request.user.role != User.SUPER_ADMIN:
        messages.error(request, "Only a Super Admin can add branches.")
        return redirect("branch_list")

    if request.method == "POST":

        form = BranchForm(request.POST)

        if form.is_valid():

            form.save()

            messages.success(
                request,
                "Branch created successfully!"
            )

            return redirect("branch_list")

    else:

        form = BranchForm()

    return render(
        request,
        "admin_panel/branches/branch_create.html",
        {
            "form": form,
        }
    )


@login_required
def all_staff_view(request):
    staff_members = in_my_branch(User.objects.filter(
        role=User.STAFF
    ), request.user).select_related("branch")

    return render(
        request,
        "admin_panel/staff/all_staff.html",
        {
            "staff_members": staff_members
        }
    )


@login_required
def delete_staff_view(request, staff_id):
    staff = get_object_or_404(
        in_my_branch(User.objects.all(), request.user),
        id=staff_id,
        role=User.STAFF
    )

    if request.method == "POST":
        staff.delete()
        messages.success(request, "Staff deleted successfully.")

    return redirect("all_staff")


@login_required
def delete_admin_view(request, admin_id):
    # Only a Super Admin can remove admins. Admins cannot remove other admins.
    if request.user.role != User.SUPER_ADMIN:
        messages.error(request, "Only a Super Admin can remove admins.")
        return redirect("all_admins")

    admin = get_object_or_404(
        User,
        id=admin_id,
        role=User.ADMIN,
    )

    if request.method == "POST":
        # Block self-deletion
        if admin.pk == request.user.pk:
            messages.error(request, "You can't delete your own account.")
            return redirect("all_admins")

        # Keep at least one admin in the system
        if User.objects.filter(role=User.ADMIN, is_active=True).count() <= 1:
            messages.error(request, "At least one admin must remain.")
            return redirect("all_admins")

        admin.delete()
        messages.success(request, "Admin deleted successfully.")

    return redirect("all_admins")

@login_required
def edit_staff_view(request, staff_id):

    staff = get_object_or_404(
        in_my_branch(User.objects.all(), request.user),
        id=staff_id,
        role=User.STAFF
    )

    branches = branches_for(request.user)

    if request.method == "POST":

        staff.username = request.POST.get("username")
        staff.first_name = request.POST.get("first_name")
        staff.last_name = request.POST.get("last_name")
        staff.email = request.POST.get("email")

        branch_id = request.POST.get("branch")

        if branch_id:
            staff.branch = get_object_or_404(
                branches_for(request.user),
                id=branch_id
            )
        else:
            staff.branch = None

        staff.is_approved = request.POST.get("is_approved") == "on"
        staff.is_active = request.POST.get("is_active") == "on"

        password = request.POST.get("password")

        # Change password only if entered
        if password:
            staff.password = make_password(password)

        staff.save()

        messages.success(
            request,
            "Staff details updated successfully."
        )

        return redirect("all_staff")

    return render(
        request,
        "admin_panel/staff/edit_staff.html",
        {
            "staff": staff,
            "branches": branches
        }
    )

@login_required
def add_admin_view(request):

    # Admin accounts are created only in the Super Admin module (they need a branch).
    if request.user.role != User.SUPER_ADMIN:
        messages.error(request, "Only a Super Admin can add admins.")
        return redirect("all_admins")
    return redirect("super_admin_create")

    if request.method == "POST":

        username = request.POST.get("username")
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        email = request.POST.get("email")
        password = request.POST.get("password")

        if not (username and first_name and last_name and email and password):
            messages.error(request, "Please fill in every field.")
            return redirect("add_admin")

        try:
            validate_password(password)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return redirect("add_admin")

        # Check username
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect("add_admin")

        # Check email
        if email and User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists.")
            return redirect("add_admin")

        # Create admin
        User.objects.create(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=make_password(password),
            role=User.ADMIN,
            is_active=True,
            is_approved=True,
        )

        messages.success(
            request,
            "Admin account created successfully."
        )

        return redirect("add_admin")

    return render(
        request,
        "admin_panel/admin/add_admin.html"
    )

@login_required
def all_admins_view(request):

    if not is_admin_role(request.user):
        return redirect("all_staff")

    # Only Admin accounts are listed. Super Admins never appear on this page.
    admins = in_my_branch(User.objects.filter(
        role=User.ADMIN
    ), request.user).order_by("id")

    return render(
        request,
        "admin_panel/admin/all_admins.html",
        {
            "admins": admins
        }
    )




@login_required
def delete_branch_view(request, branch_id):
    # Only a Super Admin can delete branches
    if request.user.role != User.SUPER_ADMIN:
        messages.error(request, "Only a Super Admin can delete branches.")
        return redirect("branch_list")

    branch = get_object_or_404(Branch, id=branch_id)

    if request.method == "POST":
        # Don't allow deleting a branch that still has reports
        if DailyReport.objects.filter(branch=branch).exists():
            messages.error(
                request,
                f"Can't delete '{branch.name}' because it has daily reports linked to it."
            )
            return redirect("branch_list")

        try:
            branch_name = branch.name
            branch.delete()
            messages.success(request, f"Branch '{branch_name}' deleted successfully.")
        except ProtectedError:
            messages.error(
                request,
                f"Can't delete '{branch.name}' because other records are linked to it."
            )

    return redirect("branch_list")





def is_admin_or_staff(user):
    """Check if user is admin or has staff permission"""
    return is_admin_role(user) or user.is_staff or user.groups.filter(name__in=['Admin', 'HR']).exists()

def reviewable_leaves(user):
    """The leave rows this user may look at and decide on.

    An Admin sees the staff leave of their own branch. A Super Admin sees all staff and
    admin leave. Admin leave is decided by a Super Admin only, and nobody reviews their own leave.
    """
    rows = in_my_branch(LeaveApplication.objects.all(), user, "staff").exclude(staff=user)
    if not is_super_admin(user):
        rows = rows.filter(staff__role=User.STAFF)
    return rows


@login_required
@user_passes_test(is_admin_or_staff)
def admin_leave_dashboard(request):
    """Admin dashboard - overview of all leave applications"""
    pending = reviewable_leaves(request.user).filter(status='pending').count()
    approved = reviewable_leaves(request.user).filter(status='approved').count()
    rejected = reviewable_leaves(request.user).filter(status='rejected').count()
    
    # Recent applications
    recent_applications = reviewable_leaves(request.user)[:10]
    
    context = {
        'pending_count': pending,
        'approved_count': approved,
        'rejected_count': rejected,
        'recent_applications': recent_applications,
    }
    
    return render(request, 'admin_panel/leave_admin_dashboard.html', context)

@login_required
@user_passes_test(is_admin_or_staff)
def admin_leave_list(request):
    """Admin view - list all leave applications with filters"""
    applications = reviewable_leaves(request.user)
    
    # Filters
    status_filter = request.GET.get('status')
    staff_filter = request.GET.get('staff')
    
    if status_filter:
        applications = applications.filter(status=status_filter)
    
    if staff_filter:
        applications = applications.filter(staff__username__icontains=staff_filter)
    
    # Sorting
    sort_by = request.GET.get('sort', '-applied_date')
    applications = applications.order_by(sort_by)
    
    context = {
        'applications': applications,
        'status_filter': status_filter,
        'staff_filter': staff_filter,
        'statuses': ['pending', 'approved', 'rejected'],
    }
    
    return render(request, 'admin_panel/leave_admin_list.html', context)

@login_required
@user_passes_test(is_admin_or_staff)
def admin_review_leave(request, application_id):
    """Admin reviews and approves/rejects leave application"""
    application = get_object_or_404(reviewable_leaves(request.user), id=application_id)
    
    if request.method == 'POST':
        form = LeaveApprovalForm(request.POST, instance=application)
        if form.is_valid():
            app = form.save(commit=False)
            app.approved_by = request.user
            app.decision_date = timezone.now()
            app.save()
            
            status_text = '✓ Approved' if app.status == 'approved' else '✗ Rejected'
            messages.success(request, f'Leave application {status_text}')
            return redirect('admin_leave_list')
    else:
        form = LeaveApprovalForm(instance=application)
    
    context = {
        'application': application,
        'form': form,
    }
    
    return render(request, 'admin_panel/leave_admin_review.html', context)

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from staff_panel.models import LeaveApplication, Attendance # Adjust import based on your app structure

@login_required
def all_leave_requests(request):
    """
    Admin view for reviewing all leave requests with search and filter functionality.
    """

    # Get all leave requests with optimized database queries
    leave_requests = reviewable_leaves(request.user).select_related(
        'staff', 'staff__branch'
    ).order_by('-applied_date')

    # ===== SEARCH FUNCTIONALITY =====
    search_query = request.GET.get('search', '').strip()
    if search_query:
        leave_requests = leave_requests.filter(
            staff__first_name__icontains=search_query
        ) | leave_requests.filter(
            staff__last_name__icontains=search_query
        ) | leave_requests.filter(
            staff__username__icontains=search_query
        )

    # ===== STATUS FILTER =====
    status_filter = request.GET.get('status', '').strip().lower()  # ← Convert to lowercase
    if status_filter and status_filter in ['pending', 'approved', 'rejected']:
        leave_requests = leave_requests.filter(status=status_filter)  # ← Exact match

    # ===== PAGINATION =====
    paginator = Paginator(leave_requests, 10)
    page_number = request.GET.get('page', 1)
    leave_requests_paginated = paginator.get_page(page_number)

    context = {
        'leave_requests': leave_requests_paginated,
        'search_query': search_query,
        'status_filter': status_filter,
    }

    return render(request, 'admin_panel/leave/all_leave_approval.html', context)




# ===== EDIT LEAVE REQUEST =====
@login_required
def edit_leave(request, leave_id):
    """
    View/Edit a leave request status.
    Allows admin to change status from Pending to Approved or Rejected.
    """
    try:
        leave = reviewable_leaves(request.user).select_related('staff', 'staff__branch').get(id=leave_id)
    except LeaveApplication.DoesNotExist:
        return redirect('all_leave_requests')

    if request.method == 'POST':
        # Update leave status
        new_status = request.POST.get('status', leave.status).strip()
        
        # Validate status
        valid_statuses = ['pending', 'approved', 'rejected']
        if new_status in valid_statuses:
            leave.status = new_status
            leave.save()
        
        return redirect('all_leave_requests')

    # Get status choices for dropdown
    status_choices = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    context = {
        'leave': leave,
        'status_choices': status_choices,
    }

    return render(request, 'admin_panel/leave/edit_leave.html', context)


@login_required
def delete_leave_request(request, pk):
    """Admin deletes one staff leave request. Admins only, and only by POST."""
    from django.urls import reverse
    from django.utils.http import url_has_allowed_host_and_scheme

    if not is_admin_role(request.user):
        raise PermissionDenied
    if request.method != 'POST':
        return redirect('all_leave_requests')

    leave = get_object_or_404(reviewable_leaves(request.user), pk=pk)
    staff_name = leave.staff.full_name or leave.staff.username
    summary = f"{leave.leave_type.name} ({leave.start_date:%d %b %Y} to {leave.end_date:%d %b %Y})"
    leave.delete()
    messages.success(request, f"Deleted {summary} for {staff_name}.")

    # Go back to the page the admin came from (same filters), but only to this site.
    next_url = request.POST.get('next', '')
    if not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        next_url = reverse('all_leave_requests')
    return redirect(next_url)


@login_required
def approve_leave(request, pk):  # ← CHANGED to pk
    if not is_admin_role(request.user):
        raise PermissionDenied
    if request.method == 'POST':
        try:
            leave = reviewable_leaves(request.user).get(id=pk)
            leave.status = 'approved'
            leave.approved_by = request.user
            leave.decision_date = timezone.now()
            leave.save()
            messages.success(request, '✓ Leave approved!')
        except LeaveApplication.DoesNotExist:
            messages.error(request, 'Leave not found')
    
    return redirect(request.META.get('HTTP_REFERER', 'all_leave_requests'))


@login_required
def reject_leave(request, pk):  # ← CHANGED to pk
    if not is_admin_role(request.user):
        raise PermissionDenied
    if request.method == 'POST':
        try:
            leave = reviewable_leaves(request.user).get(id=pk)
            leave.status = 'rejected'
            leave.approved_by = request.user
            leave.decision_date = timezone.now()
            leave.rejection_reason = request.POST.get('reason', '')
            leave.save()
            messages.success(request, '✓ Leave rejected!')
        except LeaveApplication.DoesNotExist:
            messages.error(request, 'Leave not found')
    
    return redirect(request.META.get('HTTP_REFERER', 'all_leave_requests'))

# admin_panel/views.py - Add these views



@login_required
def leavetype_list(request):
    """List all leave types"""
    if not is_admin_role(request.user):
        raise PermissionDenied
    
    leave_types = LeaveType.objects.all().order_by('name')
    
    context = {
        'leave_types': leave_types,
    }
    
    return render(request, 'admin_panel/leave/leavetype_list.html', context)

@login_required
def leavetype_create(request):
    """Create new leave type"""
    if not is_admin_role(request.user):
        raise PermissionDenied
    
    if request.method == 'POST':
        form = LeaveTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Leave type created successfully!')
            return redirect('leavetype_list')
    else:
        form = LeaveTypeForm()
    
    context = {
        'form': form,
        'title': 'Create Leave Policy',
    }
    
    return render(request, 'admin_panel/leave/leavetype_form.html', context)

@login_required
def leavetype_edit(request, leavetype_id):
    """Edit leave type"""
    if not is_admin_role(request.user):
        raise PermissionDenied
    
    leave_type = get_object_or_404(LeaveType, id=leavetype_id)
    
    if request.method == 'POST':
        form = LeaveTypeForm(request.POST, instance=leave_type)
        if form.is_valid():
            form.save()
            messages.success(request, 'Leave type updated successfully!')
            return redirect('leavetype_list')
    else:
        form = LeaveTypeForm(instance=leave_type)
    
    context = {
        'form': form,
        'leave_type': leave_type,
        'title': 'Edit Leave Policy',
    }
    
    return render(request, 'admin_panel/leave/leavetype_form.html', context)

@login_required
def leavetype_delete(request, leavetype_id):
    """Delete leave type"""
    if not is_admin_role(request.user):
        raise PermissionDenied
    
    leave_type = get_object_or_404(LeaveType, id=leavetype_id)
    
    if request.method == 'POST':
        if leave_type.is_builtin:
            messages.error(request, f"'{leave_type.name}' is a built-in leave type and cannot be deleted.")
            return redirect('leavetype_list')
        leave_type.delete()
        messages.success(request, 'Leave type deleted successfully!')
        return redirect('leavetype_list')
    
    context = {
        'leave_type': leave_type,
    }
    
    return render(request, 'admin_panel/leave/leavetype_confirm_delete.html', context)


# ---------------------------------------------------------------
# Expenses: the list the admin adds here is the dropdown staff
# see when they enter expenses in their reports.
# ---------------------------------------------------------------

@login_required
def expensetype_list(request):
    """List the expenses staff can choose from"""
    if not is_admin_role(request.user):
        raise PermissionDenied

    expense_types = ExpenseType.objects.all().order_by('name')

    return render(request, 'admin_panel/expense/expensetype_list.html', {
        'expense_types': expense_types,
    })


@login_required
def expensetype_create(request):
    """Add an expense that staff can choose"""
    if not is_admin_role(request.user):
        raise PermissionDenied

    if request.method == 'POST':
        form = ExpenseTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Expense added. Staff can now choose it when they enter expenses.')
            return redirect('expensetype_list')
    else:
        form = ExpenseTypeForm()

    return render(request, 'admin_panel/expense/expensetype_form.html', {
        'form': form,
        'title': 'Add Expense',
    })


@login_required
def expensetype_edit(request, expensetype_id):
    """Rename or switch off an expense"""
    if not is_admin_role(request.user):
        raise PermissionDenied

    expense_type = get_object_or_404(ExpenseType, id=expensetype_id)

    if request.method == 'POST':
        form = ExpenseTypeForm(request.POST, instance=expense_type)
        if form.is_valid():
            form.save()
            messages.success(request, 'Expense updated successfully!')
            return redirect('expensetype_list')
    else:
        form = ExpenseTypeForm(instance=expense_type)

    return render(request, 'admin_panel/expense/expensetype_form.html', {
        'form': form,
        'expense_type': expense_type,
        'title': 'Edit Expense',
    })


@login_required
def expensetype_delete(request, expensetype_id):
    """Delete an expense. Reports already saved keep the name they were entered with."""
    if not is_admin_role(request.user):
        raise PermissionDenied

    expense_type = get_object_or_404(ExpenseType, id=expensetype_id)

    if request.method == 'POST':
        expense_type.delete()
        messages.success(request, 'Expense deleted. Old reports keep the name they were saved with.')
        return redirect('expensetype_list')

    return render(request, 'admin_panel/expense/expensetype_confirm_delete.html', {
        'expense_type': expense_type,
    })



# ---------------------------------------------------------------
# Requirements: staff send them; the admin sees only the sent ones and approves.
# ---------------------------------------------------------------

@login_required
def admin_requirements(request):
    """Requirements sent by staff. Drafts are never stored, so only sent ones are listed."""
    if not is_admin_role(request.user):
        raise PermissionDenied

    status = request.GET.get('status', 'all')
    requirements = in_my_branch(Requirement.objects.select_related('staff', 'staff__branch', 'approved_by'), request.user, "staff")

    if status == 'pending':
        requirements = requirements.filter(status=Requirement.PENDING)
    elif status == 'approved':
        requirements = requirements.filter(status=Requirement.APPROVED)
    else:
        status = 'all'

    context = {
        'requirements': requirements,
        'status': status,
        'all_count': in_my_branch(Requirement.objects.all(), request.user, "staff").count(),
        'pending_count': in_my_branch(Requirement.objects.filter(status=Requirement.PENDING), request.user, "staff").count(),
        'approved_count': in_my_branch(Requirement.objects.filter(status=Requirement.APPROVED), request.user, "staff").count(),
    }

    return render(request, 'admin_panel/requirements/requirements_list.html', context)


@login_required
def admin_approve_requirement(request, requirement_id):
    """Approve a sent requirement. The staff member sees the approval on their own page."""
    if not is_admin_role(request.user):
        raise PermissionDenied

    requirement = get_object_or_404(in_my_branch(Requirement.objects.all(), request.user, "staff"), id=requirement_id)

    if request.method == 'POST':
        if requirement.is_approved:
            messages.info(request, 'This requirement is already approved.')
        else:
            requirement.status = Requirement.APPROVED
            requirement.approved_at = timezone.now()
            requirement.approved_by = request.user
            requirement.save()
            name = requirement.staff.full_name or requirement.staff.username
            messages.success(request, f"Approved the requirement from {name}.")

    return redirect('admin_requirements')


# views.py - Add this to your admin_salary_views

from django.db import models
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.core.paginator import Paginator
from django.conf import settings
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import datetime

from .models import Salary

# Don't import StaffUser - use get_user_model() instead
@login_required
def admin_salary_manage(request):
    """Unified salary management page - add, edit, delete, view all"""
    
    # Get all salaries with staff info
    salaries = in_my_branch(Salary.objects.all(), request.user, "staff").select_related('staff', 'approved_by').order_by('-month')
    
    # Filter by status if provided
    status = request.GET.get('status', '')
    if status:
        salaries = salaries.filter(status=status)
    
    # Filter by month if provided
    month = request.GET.get('month', '')
    if month:
        salaries = salaries.filter(month=month)
    
    # Search by staff name
    search = request.GET.get('search', '')
    if search:
        salaries = salaries.filter(
            staff__first_name__icontains=search
        ) | salaries.filter(
            staff__last_name__icontains=search
        )
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(salaries, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    total_salaries = in_my_branch(Salary.objects.all(), request.user, "staff").count()
    total_amount = in_my_branch(Salary.objects.all(), request.user, "staff").filter(status='paid').aggregate(
        total=models.Sum('net_salary')
    )['total'] or 0
    pending_count = in_my_branch(Salary.objects.all(), request.user, "staff").filter(status='pending_approval').count()
    paid_count = in_my_branch(Salary.objects.all(), request.user, "staff").filter(status='paid').count()
    
    payroll_month = parse_month(request.GET.get('payroll_month')) or timezone.localdate().replace(day=1)
    rate_rows = staff_payroll_rows(payroll_month, in_my_branch(User.objects.filter(role=User.STAFF, is_approved=True), request.user))

    context = {
        'page_obj': page_obj,
        'salaries': page_obj.object_list,
        'total_salaries': total_salaries,
        'total_amount': total_amount,
        'pending_count': pending_count,
        'paid_count': paid_count,
        'status_filter': status,
        'month_filter': month,
        'search_query': search,
        'rate_rows': rate_rows,
        'payroll_month': payroll_month,
    }
    
    return render(request, 'admin_panel/salary/salary_management.html', context)


@login_required
@require_http_methods(['POST'])
def admin_salary_add_staff(request):
    """Add salary for a staff member"""
    
    staff_id = request.POST.get('staff_id')
    month = request.POST.get('month')
    basic_salary = request.POST.get('basic_salary')
    calculation_method = request.POST.get('calculation_method', 'automatic')
    attended_days = request.POST.get('attended_days', 0)
    
    try:
        User = get_user_model()
        staff = in_my_branch(User.objects.all(), request.user).get(id=staff_id)
        
        # The month box sends 'YYYY-MM'; store the first day of that month.
        from datetime import date as _date
        _year, _mon = (int(x) for x in month[:7].split('-'))
        month_date = _date(_year, _mon, 1)

        # Check if exists
        salary_exists = in_my_branch(Salary.objects.all(), request.user, "staff").filter(staff=staff, month=month_date).exists()
        if salary_exists:
            return JsonResponse({'success': False, 'error': 'Salary already exists for this month'})
        
        # Create salary
        salary = Salary(
            staff=staff,
            month=month_date,
            basic_salary=Decimal(basic_salary)
        )
        
        if calculation_method == 'automatic':
            salary.calculate_salary()
        else:
            salary.attended_days = int(attended_days)
            salary.working_days = salary.calculate_working_days()
            salary.leave_days = salary.working_days - salary.attended_days
            if salary.working_days > 0:
                salary.per_day_salary = salary.basic_salary / Decimal(salary.working_days)
                salary.leave_deduction = Decimal(salary.leave_days) * salary.per_day_salary
            salary.net_salary = salary.basic_salary - salary.leave_deduction
        
        salary.status = 'draft'
        salary.save()
        
        return JsonResponse({'success': True, 'message': f'Salary added for {staff.get_full_name()}'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def admin_salary_edit_staff(request, salary_id):
    """Edit salary for a staff member"""
    
    salary = get_object_or_404(in_my_branch(Salary.objects.all(), request.user, "staff"), id=salary_id)
    
    if request.method == 'POST':
        basic_salary = request.POST.get('basic_salary')
        calculation_method = request.POST.get('calculation_method', 'automatic')
        attended_days = request.POST.get('attended_days', 0)
        
        salary.basic_salary = Decimal(basic_salary)
        
        if calculation_method == 'automatic':
            salary.calculate_salary()
        else:
            salary.attended_days = int(attended_days)
            salary.working_days = salary.calculate_working_days()
            salary.leave_days = salary.working_days - salary.attended_days
            if salary.working_days > 0:
                salary.per_day_salary = salary.basic_salary / Decimal(salary.working_days)
                salary.leave_deduction = Decimal(salary.leave_days) * salary.per_day_salary
            salary.net_salary = salary.basic_salary - salary.leave_deduction
        
        salary.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Salary updated successfully'
        })
    
    return render(request, 'admin_panel/salary/salary_management.html', {
        'salary': salary,
        'view_type': 'edit'
    })


@login_required
@require_http_methods(['POST'])
def admin_salary_delete_staff(request, salary_id):
    """Delete salary record"""
    
    salary = get_object_or_404(in_my_branch(Salary.objects.all(), request.user, "staff"), id=salary_id)
    staff_name = salary.staff.full_name
    
    salary.delete()
    
    return JsonResponse({
        'success': True,
        'message': f'Salary deleted for {staff_name}'
    })


@login_required
def admin_salary_detail(request, salary_id):
    """Read-only view of one salary record"""
    if not is_admin_role(request.user):
        raise PermissionDenied

    salary = get_object_or_404(in_my_branch(Salary.objects.all(), request.user, "staff").select_related('staff', 'approved_by'), id=salary_id)
    return render(request, 'admin_panel/salary/salary_detail.html', {'salary': salary})


@login_required
def admin_salary_allowance(request, staff_id):
    """Admin adds, edits or removes one staff member's salary allowance."""
    from decimal import Decimal, InvalidOperation
    from django.urls import reverse

    if not is_admin_role(request.user):
        raise PermissionDenied

    staff = get_object_or_404(in_my_branch(User.objects.all(), request.user), id=staff_id, role=User.STAFF, is_approved=True)
    name = staff.get_full_name() or staff.username
    month = parse_month(request.POST.get('payroll_month') or request.GET.get('payroll_month')) \
        or timezone.localdate().replace(day=1)
    back_url = f"{reverse('admin_salary_manage')}?payroll_month={month:%Y-%m}"

    if request.method == 'POST':
        if request.POST.get('action') == 'remove':
            staff.allowance = None
            staff.save(update_fields=['allowance'])
            messages.success(request, f"Allowance removed for {name}. The staff profile no longer shows it.")
            return redirect(back_url)

        raw = request.POST.get('allowance', '').strip()
        try:
            amount = Decimal(raw).quantize(Decimal('0.01'))
        except InvalidOperation:
            messages.error(request, f"{name}: enter the allowance as a number.")
            return redirect(request.get_full_path())
        if not amount.is_finite() or amount < 0 or amount >= Decimal('100000000'):
            messages.error(request, f"{name}: enter an amount between 0 and 99999999.99.")
            return redirect(request.get_full_path())

        staff.allowance = amount
        staff.save(update_fields=['allowance'])
        messages.success(request, f"Allowance saved for {name}: ₹{amount}.")
        return redirect(back_url)

    return render(request, 'admin_panel/salary/salary_allowance.html', {
        'staff': staff,
        'allowance': staff.allowance,
        'payroll_month': month,
        'back_url': back_url,
    })


@login_required
@require_http_methods(['POST'])
def admin_salary_save_rates(request):
    """Save each staff member's per-day amount from the salary page"""
    from decimal import Decimal, InvalidOperation
    from django.urls import reverse

    if not is_admin_role(request.user):
        raise PermissionDenied

    saved = 0
    for key, raw in request.POST.items():
        if not key.startswith('monthly_'):
            continue
        staff = in_my_branch(User.objects.filter(id=key[len('monthly_'):], role=User.STAFF, is_approved=True), request.user).first()
        if staff is None:
            continue

        name = staff.get_full_name() or staff.username
        raw = raw.strip()
        if raw == '':
            new_rate = None
        else:
            try:
                new_rate = Decimal(raw).quantize(Decimal('0.01'))
            except InvalidOperation:
                messages.error(request, f"{name}: the amount is not a valid number.")
                continue
            if not new_rate.is_finite() or new_rate < 0 or new_rate >= Decimal('100000000'):
                messages.error(request, f"{name}: enter an amount between 0 and 99999999.99.")
                continue

        if staff.monthly_salary != new_rate:
            staff.monthly_salary = new_rate
            staff.save(update_fields=['monthly_salary'])
        saved += 1

    if saved:
        messages.success(request, f"Monthly salaries saved for {saved} staff member(s).")

    month = parse_month(request.POST.get('payroll_month')) or timezone.localdate().replace(day=1)
    return redirect(f"{reverse('admin_salary_manage')}?payroll_month={month:%Y-%m}")


@login_required
def branch_edit(request, branch_id):
    # Admins can see the branches but cannot change them. Only a Super Admin can.
    if request.user.role != User.SUPER_ADMIN:
        messages.error(request, "Only a Super Admin can edit branches.")
        return redirect("branch_list")

    branch = get_object_or_404(Branch, id=branch_id)

    if request.method == "POST":
        form = BranchForm(request.POST, instance=branch)
        if form.is_valid():
            form.save()
            messages.success(request, f"Branch saved as '{branch.name}'.")
            return redirect("branch_list")
    else:
        form = BranchForm(instance=branch)

    return render(request, "admin_panel/branches/branch_create.html", {"form": form, "branch": branch})
