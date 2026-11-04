from functools import wraps
from .forms import (
    WalkinServicesForm,
    RevenueBreakdownForm,
    PaymentSummaryForm,
    ExpenseItemForm,
    ExpenseFormSet,
)
from django.contrib import messages
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render,get_object_or_404

from accounts.models import User
from django.utils import timezone
from django.db.models import Q
# NEW (Imports your section-wise forms correctly)
from .models import (
    DailyReport,
    WalkInService,
    Revenue,
    PaymentSummary,
    ExpenseItem,
    Attendance
)

from staff_panel.models import LeaveApplication,CheckInCheckOut
from admin_panel.models import LeaveType
from staff_panel.forms import LeaveApplicationForm, RequirementForm
from staff_panel.models import Requirement


def staff_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapped_view(request, *args, **kwargs):
        if request.user.role != User.STAFF or not request.user.is_approved:
            raise PermissionDenied

        return view_func(request, *args, **kwargs)

    return wrapped_view


@staff_required
def dashboard(request):
    today = timezone.localdate()

    attendance = Attendance.objects.filter(
        staff=request.user,
        date=today,
    ).first()

    reports = DailyReport.objects.filter(
        staff=request.user
    ).order_by("-report_date")[:10]

    return render(
        request,
        "staff_panel/dashboard.html",
        {
            "attendance": attendance,
            "reports": reports,
        },
    )


def _parse_location(data):
    """
    Read the browser's location from a check-in or check-out form.
    Returns (latitude, longitude, accuracy_m). Missing or out-of-range values become None.
    """
    def number(key):
        try:
            return float(data.get(key, ''))
        except (TypeError, ValueError):
            return None

    lat = number('latitude')
    lng = number('longitude')
    acc = number('accuracy')
    if lat is None or lng is None or not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        return None, None, None
    if acc is None or acc < 0 or acc > 100000:
        acc = None
    return lat, lng, acc


def _approved_leave_on(staff, day):
    """The approved leave that covers this day, or None."""
    return (
        LeaveApplication.objects.filter(
            staff=staff,
            status='approved',
            start_date__lte=day,
            end_date__gte=day,
        )
        .select_related('leave_type')
        .first()
    )


def _apply_check_action(staff, action, location=(None, None, None)):
    """
    Record a check-in or check-out for today's shift. Returns (ok, message).

    Each event is saved as a CheckInCheckOut row. The Attendance row's
    check_in / check_out fields follow the latest session, so the admin
    attendance pages agree with the staff page.
    """
    if action not in ('check_in', 'check_out'):
        return False, 'Invalid action.'

    if staff.branch is None:
        return False, 'Your account does not have a branch assigned.'

    today = timezone.localdate()
    now = timezone.now()
    time_label = timezone.localtime(now).strftime('%I:%M %p')
    lat, lng, acc = location

    # On an approved leave day, neither check-in nor check-out is allowed.
    leave_today = _approved_leave_on(staff, today)
    if leave_today is not None:
        return False, (
            f'You are on approved {leave_today.leave_type.name} leave today. '
            'Check-in and check-out are locked.'
        )

    with transaction.atomic():
        if action == 'check_in':
            attendance, _ = Attendance.objects.select_for_update().get_or_create(
                staff=staff,
                date=today,
                branch=staff.branch,
            )
        else:
            attendance = (
                Attendance.objects.select_for_update()
                .filter(staff=staff, date=today, branch=staff.branch)
                .first()
            )
            if attendance is None:
                return False, 'Please check in before checking out.'

        last_activity = attendance.activities.order_by('-timestamp').first()
        clocked_in = bool(last_activity and last_activity.activity_type == 'check_in')

        if action == 'check_in':
            if clocked_in:
                return False, 'You are already checked in. Check out first.'
            CheckInCheckOut.objects.create(
                attendance=attendance,
                activity_type='check_in',
                timestamp=now,
                latitude=lat,
                longitude=lng,
                accuracy_m=acc,
            )
            attendance.check_in = now
            attendance.check_out = None
            attendance.save(update_fields=['check_in', 'check_out'])
            return True, f'Checked in at {time_label}.'

        if not clocked_in:
            return False, 'You are already checked out. Check in first.'
        CheckInCheckOut.objects.create(
            attendance=attendance,
            activity_type='check_out',
            timestamp=now,
            latitude=lat,
            longitude=lng,
            accuracy_m=acc,
        )
        attendance.check_out = now
        attendance.save(update_fields=['check_out'])
        return True, f'Checked out at {time_label}.'


def _flash_check_result(request, action):
    ok, message = _apply_check_action(request.user, action, _parse_location(request.POST))
    if ok:
        messages.success(request, message)
    else:
        messages.error(request, message)


@staff_required
def check_in(request):
    if request.method == 'POST':
        _flash_check_result(request, 'check_in')
    return redirect('staff_dashboard')


@staff_required
def check_out(request):
    if request.method == 'POST':
        _flash_check_result(request, 'check_out')
    return redirect('staff_dashboard')




from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import date, timedelta
from .models import Attendance, LeaveApplication


from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import date, timedelta
from .models import Attendance, LeaveApplication


from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import date, timedelta
from staff_panel.models import Attendance, LeaveApplication

User = get_user_model()

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import date, timedelta
from .models import Attendance, LeaveApplication

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import date, timedelta

User = get_user_model()



@login_required
def attendance_page(request):
    staff = request.user
    today = timezone.localdate()

    # Check-in and check-out are sent as a normal form POST. Handle them here and
    # redirect back to this page, so the user sees a message instead of raw JSON.
    if request.method == 'POST':
        action = request.POST.get('action')
        if action in ('check_in', 'check_out'):
            _flash_check_result(request, action)
        else:
            messages.error(request, 'Invalid action.')
        return redirect('attendance_page')

    branch = staff.branch
    if branch is None:
        messages.error(request, 'Your account does not have a branch assigned.')
        return redirect('staff_dashboard')

    current_shift = Attendance.objects.filter(
        staff=staff,
        date=today,
        branch=branch,
    ).first()

    # The button state comes from the latest check-in / check-out event.
    is_checked_in = False
    if current_shift:
        last_activity = current_shift.activities.order_by('-timestamp').first()
        is_checked_in = bool(last_activity and last_activity.activity_type == 'check_in')

    leave_today = _approved_leave_on(staff, today)

    filter_type = request.GET.get('filter', 'month')
    filter_date = request.GET.get('date')

    if filter_type == 'today':
        start_date = today
        end_date = today
        range_label = "Today"
    elif filter_type == 'week':
        start_date = today - timedelta(days=today.weekday())
        end_date = today
        range_label = "This Week"
    elif filter_type == 'month':
        start_date = today.replace(day=1)
        end_date = today
        range_label = "This Month"
    elif filter_type == 'all':
        start_date = timezone.datetime(1900, 1, 1).date()
        end_date = today
        range_label = "All Time"
    else:
        start_date = today - timedelta(days=30)
        end_date = today
        range_label = "Last 30 Days"

    attendance_records = Attendance.objects.filter(
        staff=staff,
        branch=branch,
        date__gte=start_date,
        date__lte=end_date
    ).prefetch_related('activities').order_by('-date')

    # Leave is applied for future days too, so leave rows run to the end of the chosen
    # period. Attendance rows still stop at today.
    if filter_type == 'all':
        leave_end = timezone.datetime(9999, 12, 31).date()
    elif filter_type == 'week':
        leave_end = start_date + timedelta(days=6)
    elif filter_type == 'month':
        leave_end = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    else:
        leave_end = end_date

    leave_records = LeaveApplication.objects.filter(
        staff=staff,
        start_date__lte=leave_end,
        end_date__gte=start_date,
        status__in=['approved', 'pending']
    ).select_related('leave_type').order_by('start_date')

    combined_history = []

    for record in attendance_records:
        activities = record.activities.all()
        combined_history.append({
            'type': 'attendance',
            'date': record.date,
            'activities': activities,
            'record': record,
            'check_in': record.check_in,
            'check_out': record.check_out
        })

    attendance_dates = {record.date for record in attendance_records}
    seen_leave_dates = set()

    # Approved leave first, so a day with both kinds of request shows the approved one.
    for leave in sorted(leave_records, key=lambda l: l.status != 'approved'):
        current_date = leave.start_date
        while current_date <= leave.end_date:
            if (start_date <= current_date <= leave_end
                    and current_date not in attendance_dates
                    and current_date not in seen_leave_dates):
                seen_leave_dates.add(current_date)
                combined_history.append({
                    'type': 'leave',
                    'date': current_date,
                    'leave_type': leave.leave_type.name if leave.leave_type else 'Leave',
                    'status': leave.status,
                    'leave': leave
                })
            current_date += timedelta(days=1)

    combined_history.sort(key=lambda x: x['date'], reverse=True)

    total_attendance = len([h for h in combined_history if h['type'] == 'attendance'])
    total_leave_days = len([h for h in combined_history if h['type'] == 'leave' and h['status'] == 'approved'])
    pending_leave_days = len([h for h in combined_history if h['type'] == 'leave' and h['status'] == 'pending'])

    context = {
        'current_shift': current_shift,
        'is_checked_in': is_checked_in,
        'leave_today': leave_today,
        'history': combined_history,
        'range_label': range_label,
        'filter_type': filter_type,
        'total_attendance': total_attendance,
        'total_leave_days': total_leave_days,
        'pending_leave_days': pending_leave_days,
    }

    return render(request, 'staff_panel/attendance.html', context)
@login_required
def report_dashboard(request):

    today = timezone.localdate()

    report = DailyReport.objects.filter(
        staff=request.user,
        branch=request.user.branch,
        report_date=today,
    ).order_by("-id").first()

    return render(
        request,
        "staff_panel/report_dashboard.html",
        {
            "report": report,
        }
    )


@login_required
def reports_add(request):

    reports = DailyReport.objects.filter(
        staff=request.user
    ).select_related(
        "branch"
    ).order_by(
        "-report_date",
        "-id"
    )

    return render(
        request,
        "staff_panel/add_reports/reports_add.html",
        {
            "reports": reports,
        }
    )


@login_required
def create_report(request):

    if request.method != "POST":
        return redirect("reports_add")

    report = DailyReport.objects.create(
        staff=request.user,
        branch=request.user.branch,
        report_date=timezone.localdate(),
        status=DailyReport.SUBMITTED,
    )

    messages.success(
        request,
        f"Report #{report.id} created successfully!"
    )

    return redirect(
        "report_hub",
        report_id=report.id
    )


@login_required
def report_hub(request, report_id):

    report = get_object_or_404(
        DailyReport,
        id=report_id,
        staff=request.user
    )

    return render(
        request,
        "staff_panel/add_reports/report_hub.html",
        {
            "report": report,
        }
    )

@login_required
def delete_report(request, report_id):

    if request.method != "POST":
        return redirect("reports_add")

    report = get_object_or_404(
        DailyReport,
        id=report_id,
        staff=request.user
    )

    # Don't allow approved reports to be deleted
    if report.status == DailyReport.APPROVED:
        messages.error(
            request,
            "Approved reports cannot be deleted."
        )
        return redirect("reports_add")

    report.delete()

    messages.success(
        request,
        "Report deleted successfully."
    )

    return redirect("reports_add")

def _payment_data(post):
    """Empty payment boxes count as 0, so staff only type the amounts they received."""
    data = post.copy()
    for key in ("cash", "gpay", "card"):
        if not data.get(key, "").strip():
            data[key] = "0"
    return data


@login_required
def add_walkins(request, report_id):

    report = get_object_or_404(
        DailyReport,
        id=report_id,
        staff=request.user
    )

    # Approved report cannot be edited
    if report.status == DailyReport.APPROVED:
        messages.error(
            request,
            "This report is approved and locked. Changes cannot be saved."
        )
        return redirect("reports_add")

    # Walk-ins and payments are saved together on the same sheet.
    try:
        walkins = report.walkins
    except WalkInService.DoesNotExist:
        walkins = None
    payments = PaymentSummary.objects.filter(report=report).first()

    # --------------------------------------------------
    # POST - SAVE WALK-INS AND PAYMENTS TOGETHER
    # --------------------------------------------------
    if request.method == "POST":

        form = WalkinServicesForm(
            request.POST,
            instance=walkins
        )
        payment_form = PaymentSummaryForm(
            _payment_data(request.POST),
            instance=payments
        )

        if form.is_valid() and payment_form.is_valid():

            with transaction.atomic():
                walkins = form.save(commit=False)
                walkins.report = report
                walkins.save()

                payments = payment_form.save(commit=False)
                payments.report = report
                payments.save()

            messages.success(
                request,
                "Walk-ins and payments saved successfully!"
            )

            return redirect("reports_add")

    # --------------------------------------------------
    # GET - DO NOT CREATE ANYTHING
    # --------------------------------------------------
    else:

        form = WalkinServicesForm(
            instance=walkins
        )
        payment_form = PaymentSummaryForm(
            instance=payments
        )

    return render(
        request,
        "staff_panel/add_reports/add_walkins.html",
        {
            "form": form,
            "payment_form": payment_form,
            "report": report,
            "walkins": walkins,
        }
    )

@login_required
def add_revenues(request, report_id):

    report = get_object_or_404(
        DailyReport,
        id=report_id,
        staff=request.user
    )

    # Approved report cannot be edited
    if report.status == DailyReport.APPROVED:
        messages.error(
            request,
            "This report is approved and locked. Changes cannot be saved."
        )
        return redirect("reports_add")

    # Get existing Revenue if it exists.
    # DO NOT create anything on GET.
    try:
        revenue = report.revenues
    except Revenue.DoesNotExist:
        revenue = None

    # --------------------------------------------------
    # POST - CREATE / UPDATE ONLY WHEN SAVE IS CLICKED
    # --------------------------------------------------
    if request.method == "POST":

        form = RevenueBreakdownForm(
            request.POST,
            instance=revenue
        )

        if form.is_valid():

            revenue = form.save(commit=False)
            revenue.report = report
            revenue.save()

            messages.success(
                request,
                "Revenue details saved successfully!"
            )

            return redirect("reports_add")

    # --------------------------------------------------
    # GET - DO NOT CREATE REVENUE
    # --------------------------------------------------
    else:

        form = RevenueBreakdownForm(
            instance=revenue
        )

    return render(
        request,
        "staff_panel/add_reports/add_revenue.html",
        {
            "form": form,
            "report": report,
            "revenue": revenue,
        }
    )

@login_required
def add_payments(request, report_id):
    """Payments are entered on the same sheet as the walk-ins, so this opens that sheet."""
    return redirect("add_walkins", report_id=report_id)


@login_required
def add_expenses(request, report_id):

    # Get the existing report belonging to the logged-in staff
    report = get_object_or_404(
        DailyReport,
        id=report_id,
        staff=request.user
    )

    # --------------------------------------------------
    # APPROVED REPORT = LOCKED
    # --------------------------------------------------
    if report.status == DailyReport.APPROVED:
        messages.error(
            request,
            "This report is approved and locked. Changes cannot be saved."
        )

        return redirect("expenses_history_list")

    # --------------------------------------------------
    # POST
    # --------------------------------------------------
    if request.method == "POST":

        form = ExpenseFormSet(
            request.POST,
            instance=report
        )

        if form.is_valid():

            form.save()

            messages.success(
                request,
                "Expense details saved successfully!"
            )

            return redirect("reports_add")

    # --------------------------------------------------
    # GET
    # --------------------------------------------------
    else:

        form = ExpenseFormSet(
            instance=report
        )

    return render(
        request,
        "staff_panel/add_reports/add_expenses.html",
        {
            "form": form,
            "report": report,
        }
    )





@login_required
def reports_history(request):
    # Security check: Ensure the user is either staff or admin
    if not (getattr(request.user, 'is_staff', False) or getattr(request.user, 'role', None) in ['STAFF', 'ADMIN']):
        raise PermissionDenied("You do not have permission to access the daily report add page.")
    
        
    return render(request, "staff_panel/reports_history.html")

@login_required
def walkins_history_list(request):

    if not (
        getattr(request.user, "is_staff", False)
        or getattr(request.user, "role", None) in ["STAFF", "ADMIN"]
    ):
        raise PermissionDenied(
            "You do not have permission to access walk-in history."
        )

    user_role = getattr(request.user, "role", None)

    if user_role == "ADMIN" or request.user.is_superuser:

        # Admin can see all staff data
        reports = WalkInService.objects.select_related(
            "report",
            "report__branch",
            "report__staff",
        ).all().order_by(
            "-report__report_date",
            "-id"
        )

    else:

        # Staff can see ONLY their own data
        reports = WalkInService.objects.select_related(
            "report",
            "report__branch",
            "report__staff",
        ).filter(
            report__staff=request.user
        ).order_by(
            "-report__report_date",
            "-id"
        )

    search_query = request.GET.get("q")

    if search_query:
        reports = reports.filter(
            Q(report__report_date__icontains=search_query)
            | Q(report__branch__name__icontains=search_query)
            | Q(report__staff__username__icontains=search_query)
        )

    return render(
        request,
        "staff_panel/reports_history/walkins_history_list.html",
        {
            "reports": reports,
        }
    )
@login_required
def revenue_history_list(request):
    # Security check
    if not (
        getattr(request.user, "is_staff", False)
        or getattr(request.user, "role", None) in ["STAFF", "ADMIN"]
    ):
        raise PermissionDenied(
            "You do not have permission to access the revenue history page."
        )

    # Admin sees all branches
    # Staff sees only their own branch
    user_role = getattr(request.user, "role", None)

    if user_role == "ADMIN" or request.user.is_superuser:
        revenues = Revenue.objects.select_related(
            "report",
            "report__branch",
            "report__staff",
        ).all().order_by(
            "-report__report_date",
            "-id"
        )
    else:
        revenues = Revenue.objects.select_related(
            "report",
            "report__branch",
            "report__staff",
        ).filter(
            report__branch=request.user.branch
        ).order_by(
            "-report__report_date",
            "-id"
        )

    # Search by date, branch, or staff username
    search_query = request.GET.get("q")

    if search_query:
        revenues = revenues.filter(
            Q(report__report_date__icontains=search_query)
            | Q(report__branch__name__icontains=search_query)
            | Q(report__staff__username__icontains=search_query)
        )

    return render(
        request,
        "staff_panel/reports_history/revenue_history_list.html",
        {
            "revenues": revenues,
            "search_query": search_query,
        }
    )

@login_required
def payments_history_list(request):
    """Payments are listed with the walk-ins, so this opens the walk-ins history."""
    return redirect("walkins_history_list")


@login_required
def expenses_history_list(request):

    if not (
        getattr(request.user, "is_staff", False)
        or getattr(request.user, "role", None) in ["STAFF", "ADMIN"]
    ):
        raise PermissionDenied(
            "You do not have permission to access the expenses history."
        )

    user_role = getattr(request.user, "role", None)

    if user_role == "ADMIN" or request.user.is_superuser:

        reports = DailyReport.objects.prefetch_related(
            "expenses"
        ).select_related(
            "branch",
            "staff",
        ).all()

    else:

        reports = DailyReport.objects.prefetch_related(
            "expenses"
        ).select_related(
            "branch",
            "staff",
        ).filter(
            branch=request.user.branch
        )

    reports = reports.order_by(
        "-report_date",
        "-id"
    )

    # Search
    search_query = request.GET.get("q", "").strip()

    if search_query:

        reports = reports.filter(
            Q(report_date__icontains=search_query)
            | Q(branch__name__icontains=search_query)
            | Q(staff__username__icontains=search_query)
        )

    return render(
        request,
        "staff_panel/reports_history/expenses_history_list.html",
        {
            "reports": reports,
            "search_query": search_query,
            "is_admin": (
                user_role == "ADMIN"
                or request.user.is_superuser
            ),
        }
    )


@login_required
def view_expense_report(request, report_id):

    report = get_object_or_404(
        DailyReport.objects.prefetch_related("expenses").select_related(
            "branch",
            "staff",
        ),
        id=report_id
    )

    # Staff can only view their branch
    if (
        getattr(request.user, "role", None) != "ADMIN"
        and not request.user.is_superuser
        and report.branch != request.user.branch
    ):
        raise PermissionDenied(
            "You do not have permission to view this report."
        )

    return render(
        request,
        "staff_panel/reports_history/view_expenses_report.html",
        {
            "report": report,
        }
    )

@login_required
def delete_expense_report(request, report_id):

    report = get_object_or_404(
        DailyReport,
        id=report_id
    )

    is_admin = (
        getattr(request.user, "role", None) == "ADMIN"
        or request.user.is_superuser
    )

    # Approved reports can only be deleted by ADMIN.
    if report.status == DailyReport.APPROVED and not is_admin:
        messages.error(
            request,
            "This report has been approved and is locked. "
            "An administrator must reject it before it can be deleted."
        )

        return redirect(
            "view_expense_report",
            report_id=report.id
        )

    # Non-admin users can only delete reports from their own branch.
    if (
        not is_admin
        and report.branch != request.user.branch
    ):
        raise PermissionDenied(
            "You do not have permission to delete this report."
        )

    # Only POST can permanently delete the report.
    if request.method != "POST":
        return redirect(
            "view_expense_report",
            report_id=report.id
        )

    report_date = report.report_date

    # ExpenseItem.report uses CASCADE,
    # so all expenses belonging to this report
    # will also be deleted.
    report.delete()

    messages.success(
        request,
        f"Expense report for {report_date} deleted successfully."
    )

    return redirect("expenses_history_list")

@login_required
def edit_walkins_section(request, report_id):

    report = get_object_or_404(
        DailyReport,
        id=report_id
    )

    walkins = get_object_or_404(
        WalkInService,
        report=report
    )
    payments = PaymentSummary.objects.filter(report=report).first()

    if (
        report.status == DailyReport.APPROVED
        and getattr(request.user, "role", None) != "ADMIN"
    ):
        messages.error(
            request,
            "This report has already been approved and cannot be edited."
        )
        return redirect("walkins_history_list")

    if request.method == "POST":

        form = WalkinServicesForm(
            request.POST,
            instance=walkins
        )
        payment_form = PaymentSummaryForm(
            _payment_data(request.POST),
            instance=payments
        )

        if form.is_valid() and payment_form.is_valid():

            with transaction.atomic():
                form.save()

                payment_form.instance.report = report
                payment_form.save()

            messages.success(
                request,
                "Walk-ins and payments updated successfully!"
            )

            return redirect("walkins_history_list")

    else:
        form = WalkinServicesForm(
            instance=walkins
        )
        payment_form = PaymentSummaryForm(
            instance=payments
        )

    return render(
        request,
        "staff_panel/edit_walkins.html",
        {
            "form": form,
            "payment_form": payment_form,
            "report": report,
            "walkins": walkins,
        }
    )

@login_required
def edit_revenue_section(request, report_id):

    report = get_object_or_404(
        DailyReport,
        pk=report_id
    )

    revenue = get_object_or_404(
        Revenue,
        report=report
    )

    if (
        report.status == DailyReport.APPROVED
        and getattr(request.user, "role", None) != "ADMIN"
    ):
        messages.error(
            request,
            "This report has already been approved and cannot be edited."
        )
        return redirect("revenue_history_list")

    if request.method == "POST":

        form = RevenueBreakdownForm(
            request.POST,
            instance=revenue
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Revenue updated successfully!"
            )

            return redirect("revenue_history_list")

    else:

        form = RevenueBreakdownForm(
            instance=revenue
        )

    return render(
        request,
        "staff_panel/edit_revenue.html",
        {
            "form": form,
            "report": report,
            "revenue": revenue,
        }
    )

@login_required
def edit_payments_section(request, report_id):
    """Payments are edited on the same sheet as the walk-ins, so this opens that sheet."""
    return redirect("edit_walkins_section", report_id=report_id)


@login_required
def edit_expenses_section(request, report_id):

    # Get the main report
    report = get_object_or_404(
        DailyReport,
        id=report_id
    )

    # Prevent editing approved reports
    if (
        report.status == DailyReport.APPROVED
        and getattr(request.user, "role", None) != "ADMIN"
        and not request.user.is_superuser
    ):
        messages.error(
            request,
            "This report has already been approved and cannot be edited."
        )
        return redirect("expenses_history_list")

    # POST
    if request.method == "POST":

        form = ExpenseFormSet(
            request.POST,
            instance=report
        )

        if form.is_valid():

            form.save()

            messages.success(
                request,
                "Expense details updated successfully!"
            )

            return redirect("expenses_history_list")

    # GET
    else:

        form = ExpenseFormSet(
            instance=report
        )

    return render(
        request,
        "staff_panel/edit_expenses.html",
        {
            "form": form,
            "report": report,
        }
    )



@login_required
def staff_profile(request):
    """My Profile: my account details."""
    return render(
        request,
        "staff_panel/profile/staff_profile.html",
        {
            "user": request.user,
        }
    )


@login_required
def staff_salary_management(request):
    """Salary Management: my monthly salary and salary history."""
    from admin_panel.payroll import monthly_summary
    from admin_panel.models import Salary

    payroll = monthly_summary(request.user, timezone.localdate())

    return render(
        request,
        "staff_panel/profile/salary_management.html",
        {
            "payroll": payroll,
            # Last 6 saved salary records.
            "salary_history": Salary.objects.filter(staff=request.user).order_by('-month')[:6],
        }
    )


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from accounts.models import User


@login_required
def edit_staff_profile(request):

    user = request.user

    if request.method == "POST":

        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()

        # Validate name
        if not first_name:
            messages.error(request, "Name is required.")
            return redirect("edit_staff_profile")

        # Validate username
        if not username:
            messages.error(request, "Username is required.")
            return redirect("edit_staff_profile")

        # Validate email
        if not email:
            messages.error(request, "Email is required.")
            return redirect("edit_staff_profile")

        # Check username already exists
        if User.objects.filter(
            username=username
        ).exclude(
            id=user.id
        ).exists():

            messages.error(
                request,
                "This username is already in use."
            )

            return redirect("edit_staff_profile")

        # Check email already exists
        if User.objects.filter(
            email=email
        ).exclude(
            id=user.id
        ).exists():

            messages.error(
                request,
                "This email address is already in use."
            )

            return redirect("edit_staff_profile")

        # Update allowed fields only
        user.first_name = first_name
        user.last_name = last_name
        user.username = username
        user.email = email

        user.save()

        messages.success(
            request,
            "Profile updated successfully."
        )

        return redirect("staff_profile")

    return render(
        request,
        "staff_panel/profile/edit_staff_profile.html",
        {
            "user": user,
        }
    )






from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import date
from dateutil.relativedelta import relativedelta
from admin_panel.models import Salary

@login_required
def staff_leave_dashboard(request):
    """Staff Leave page - view own leave applications"""
    user = request.user
    user_leaves = LeaveApplication.objects.filter(staff=user)
    
    context = {
        'pending_leaves': user_leaves.filter(status='pending'),
        'approved_leaves': user_leaves.filter(status='approved'),
        'rejected_leaves': user_leaves.filter(status='rejected'),
        'total_pending': user_leaves.filter(status='pending').count(),
        'total_approved': user_leaves.filter(status='approved').count(),
    }
    
    return render(request, 'staff_panel/leave/leave_dashboard.html', context)

@login_required
def apply_leave(request):
    """Staff applies for leave"""
    if request.method == 'POST':
        form = LeaveApplicationForm(request.POST)
        if form.is_valid():
            application = form.save(commit=False)
            application.staff = request.user
            application.save()
            
            messages.success(request, 'Leave application submitted successfully! ✓')
            return redirect('staff_leave_dashboard')
        else:
            messages.error(request, 'Please correct the errors below')
    else:
        form = LeaveApplicationForm()
    
    context = {
        'form': form,
        'leave_types': LeaveType.objects.filter(is_active=True),
    }
    
    return render(request, 'staff_panel/leave/apply_leave.html', context)

@login_required
def leave_application_detail(request, application_id):
    """View leave application details"""
    application = get_object_or_404(LeaveApplication, id=application_id)
    
    # Check if staff can view their own application
    if application.staff != request.user:
        messages.error(request, 'You do not have permission to view this')
        return redirect('staff_leave_dashboard')
    
    return render(request, 'staff_panel/leave/leave_detail.html', {'application': application})


@login_required
def staff_requirements(request):
    """Requirements: send a requirement to the admin, and see the status of my own."""
    if request.method == "POST":
        form = RequirementForm(request.POST)
        if form.is_valid():
            requirement = form.save(commit=False)
            requirement.staff = request.user
            requirement.save()
            messages.success(request, "Requirement sent to the admin.")
            return redirect("staff_requirements")
    else:
        # Nothing is saved on a plain visit; a row is created only when the form is sent.
        form = RequirementForm()

    # Only my own requirements are shown here.
    my_requirements = Requirement.objects.filter(staff=request.user).select_related("approved_by")

    return render(
        request,
        "staff_panel/requirements/requirements.html",
        {
            "form": form,
            "requirements": my_requirements,
        }
    )