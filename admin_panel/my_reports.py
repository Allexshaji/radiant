"""An admin's own daily reports.

These pages work the same way as the staff daily report pages: the same forms,
the same steps (walk-ins and payments, revenue, expenses) and the same locks.
The difference is the owner. An admin only sees and changes reports that the
admin created for their own branch. Staff reports are not shown here; they stay
in the "All Staff Reports" pages.

An admin can send a report to the Super Admin from its report page. The Super Admin
sees it in "Received Reports", grouped by branch.
"""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.access import ADMIN_ROLES
from staff_panel.forms import (
    ExpenseFormSet,
    PaymentSummaryForm,
    RevenueBreakdownForm,
    WalkinServicesForm,
)
from staff_panel.models import DailyReport, PaymentSummary, Revenue, WalkInService
from staff_panel.views import _payment_data

from .models import ReportSubmission


def my_reports_required(view):
    """Only an admin with a branch keeps daily reports. Anyone else is sent back to the admin dashboard."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if getattr(user, "role", None) not in ADMIN_ROLES:
            raise PermissionDenied
        if not user.branch_id:
            messages.error(request, "Your account has no branch, so daily reports cannot be used.")
            return redirect("admin_dashboard")
        return view(request, *args, **kwargs)

    return login_required(wrapper)


def _my_report(request, report_id):
    """One of this admin's own reports. Any other report is not found here."""
    return get_object_or_404(
        DailyReport.objects.select_related("branch", "staff"),
        id=report_id,
        staff=request.user,
    )


def _my_reports(user):
    return DailyReport.objects.filter(staff=user).select_related("branch", "staff")


def _is_sent(report):
    return ReportSubmission.objects.filter(report=report).exists()


# ----------------------------------------------------------------
# Report list and report page
# ----------------------------------------------------------------

@my_reports_required
def report_dashboard(request):
    today = timezone.localdate()

    report = DailyReport.objects.filter(
        staff=request.user,
        branch=request.user.branch,
        report_date=today,
    ).order_by("-id").first()

    return render(
        request,
        "admin_panel/my_reports/report_dashboard.html",
        {"report": report},
    )


@my_reports_required
def reports_add(request):
    reports = _my_reports(request.user).select_related(
        "super_admin_submission",
    ).order_by("-report_date", "-id")

    return render(
        request,
        "admin_panel/my_reports/reports_add.html",
        {"reports": reports},
    )


@my_reports_required
def create_report(request):
    if request.method != "POST":
        return redirect("admin_reports_add")

    report = DailyReport.objects.create(
        staff=request.user,
        branch=request.user.branch,
        report_date=timezone.localdate(),
        status=DailyReport.SUBMITTED,
    )

    messages.success(request, f"Report #{report.id} created successfully!")

    return redirect("admin_report_hub", report_id=report.id)


@my_reports_required
def report_hub(request, report_id):
    report = _my_report(request, report_id)

    submission = ReportSubmission.objects.filter(report=report).select_related("sent_by").first()

    return render(
        request,
        "admin_panel/my_reports/report_hub.html",
        {
            "report": report,
            "submission": submission,
        },
    )


@my_reports_required
def delete_report(request, report_id):
    if request.method != "POST":
        return redirect("admin_reports_add")

    report = _my_report(request, report_id)

    if report.status == DailyReport.APPROVED:
        messages.error(request, "Approved reports cannot be deleted.")
        return redirect("admin_reports_add")

    if _is_sent(report):
        messages.error(request, "This report was sent to the Super Admin, so it cannot be deleted.")
        return redirect("admin_report_hub", report_id=report.id)

    report.delete()

    messages.success(request, "Report deleted successfully.")

    return redirect("admin_reports_add")


@my_reports_required
@require_POST
def send_report(request, report_id):
    """Send this report to the Super Admin. Sending it again only updates the time."""
    report = _my_report(request, report_id)

    _, created = ReportSubmission.objects.update_or_create(
        report=report,
        defaults={"sent_by": request.user, "sent_at": timezone.now()},
    )

    if created:
        messages.success(request, f"Report #{report.id} sent to the Super Admin.")
    else:
        messages.success(request, f"Report #{report.id} sent to the Super Admin again.")

    return redirect("admin_report_hub", report_id=report.id)


# ----------------------------------------------------------------
# Adding parts of a report
# ----------------------------------------------------------------

@my_reports_required
def add_walkins(request, report_id):
    report = _my_report(request, report_id)

    # Approved report cannot be edited
    if report.status == DailyReport.APPROVED:
        messages.error(request, "This report is approved and locked. Changes cannot be saved.")
        return redirect("admin_reports_add")

    # Walk-ins and payments are saved together on the same sheet.
    try:
        walkins = report.walkins
    except WalkInService.DoesNotExist:
        walkins = None
    payments = PaymentSummary.objects.filter(report=report).first()

    if request.method == "POST":

        form = WalkinServicesForm(request.POST, instance=walkins)
        payment_form = PaymentSummaryForm(_payment_data(request.POST), instance=payments)

        if form.is_valid() and payment_form.is_valid():

            with transaction.atomic():
                walkins = form.save(commit=False)
                walkins.report = report
                walkins.save()

                payments = payment_form.save(commit=False)
                payments.report = report
                payments.save()

            messages.success(request, "Walk-ins and payments saved successfully!")

            return redirect("admin_reports_add")

    else:

        form = WalkinServicesForm(instance=walkins)
        payment_form = PaymentSummaryForm(instance=payments)

    return render(
        request,
        "admin_panel/my_reports/add_walkins.html",
        {
            "form": form,
            "payment_form": payment_form,
            "report": report,
            "walkins": walkins,
        },
    )


@my_reports_required
def add_revenues(request, report_id):
    report = _my_report(request, report_id)

    # Approved report cannot be edited
    if report.status == DailyReport.APPROVED:
        messages.error(request, "This report is approved and locked. Changes cannot be saved.")
        return redirect("admin_reports_add")

    try:
        revenue = report.revenues
    except Revenue.DoesNotExist:
        revenue = None

    if request.method == "POST":

        form = RevenueBreakdownForm(request.POST, instance=revenue)

        if form.is_valid():

            revenue = form.save(commit=False)
            revenue.report = report
            revenue.save()

            messages.success(request, "Revenue details saved successfully!")

            return redirect("admin_reports_add")

    else:

        form = RevenueBreakdownForm(instance=revenue)

    return render(
        request,
        "admin_panel/my_reports/add_revenue.html",
        {
            "form": form,
            "report": report,
            "revenue": revenue,
        },
    )


@my_reports_required
def add_expenses(request, report_id):
    report = _my_report(request, report_id)

    # APPROVED REPORT = LOCKED
    if report.status == DailyReport.APPROVED:
        messages.error(request, "This report is approved and locked. Changes cannot be saved.")
        return redirect("admin_expenses_history")

    if request.method == "POST":

        form = ExpenseFormSet(request.POST, instance=report)

        if form.is_valid():

            form.save()

            messages.success(request, "Expense details saved successfully!")

            return redirect("admin_reports_add")

    else:

        form = ExpenseFormSet(instance=report)

    return render(
        request,
        "admin_panel/my_reports/add_expenses.html",
        {
            "form": form,
            "report": report,
        },
    )


# ----------------------------------------------------------------
# History
# ----------------------------------------------------------------

@my_reports_required
def reports_history(request):
    return render(request, "admin_panel/my_reports/reports_history.html")


def _search_term(request):
    return request.GET.get("q", "").strip()


@my_reports_required
def walkins_history_list(request):
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

    search_query = _search_term(request)

    if search_query:
        reports = reports.filter(
            Q(report__report_date__icontains=search_query)
            | Q(report__branch__name__icontains=search_query)
        )

    return render(
        request,
        "admin_panel/my_reports/walkins_history_list.html",
        {
            "reports": reports,
            "search_query": search_query,
        },
    )


@my_reports_required
def revenue_history_list(request):
    revenues = Revenue.objects.select_related(
        "report",
        "report__branch",
        "report__staff",
    ).filter(
        report__staff=request.user
    ).order_by(
        "-report__report_date",
        "-id"
    )

    search_query = _search_term(request)

    if search_query:
        revenues = revenues.filter(
            Q(report__report_date__icontains=search_query)
            | Q(report__branch__name__icontains=search_query)
        )

    return render(
        request,
        "admin_panel/my_reports/revenue_history_list.html",
        {
            "revenues": revenues,
            "search_query": search_query,
        },
    )


@my_reports_required
def expenses_history_list(request):
    reports = DailyReport.objects.prefetch_related(
        "expenses"
    ).select_related(
        "branch",
        "staff",
    ).filter(
        staff=request.user
    ).order_by(
        "-report_date",
        "-id"
    )

    search_query = _search_term(request)

    if search_query:
        reports = reports.filter(
            Q(report_date__icontains=search_query)
            | Q(branch__name__icontains=search_query)
        )

    return render(
        request,
        "admin_panel/my_reports/expenses_history_list.html",
        {
            "reports": reports,
            "search_query": search_query,
            "is_admin": False,
        },
    )


@my_reports_required
def view_expense_report(request, report_id):
    report = get_object_or_404(
        DailyReport.objects.prefetch_related("expenses").select_related("branch", "staff"),
        id=report_id,
        staff=request.user,
    )

    return render(
        request,
        "admin_panel/my_reports/view_expenses_report.html",
        {"report": report},
    )


@my_reports_required
def delete_expense_report(request, report_id):
    report = _my_report(request, report_id)

    if report.status == DailyReport.APPROVED:
        messages.error(
            request,
            "This report is approved and locked, so it cannot be deleted."
        )
        return redirect("admin_view_expense_report", report_id=report.id)

    # Only POST can permanently delete the report.
    if request.method != "POST":
        return redirect("admin_view_expense_report", report_id=report.id)

    if _is_sent(report):
        messages.error(
            request,
            "This report was sent to the Super Admin, so it cannot be deleted."
        )
        return redirect("admin_view_expense_report", report_id=report.id)

    report_date = report.report_date

    # ExpenseItem.report uses CASCADE, so the expenses are deleted with the report.
    report.delete()

    messages.success(request, f"Expense report for {report_date} deleted successfully.")

    return redirect("admin_expenses_history")


# ----------------------------------------------------------------
# Editing a saved report
# ----------------------------------------------------------------

@my_reports_required
def edit_walkins(request, report_id):
    report = _my_report(request, report_id)

    walkins = get_object_or_404(WalkInService, report=report)
    payments = PaymentSummary.objects.filter(report=report).first()

    if report.status == DailyReport.APPROVED:
        messages.error(request, "This report has already been approved and cannot be edited.")
        return redirect("admin_walkins_history")

    if request.method == "POST":

        form = WalkinServicesForm(request.POST, instance=walkins)
        payment_form = PaymentSummaryForm(_payment_data(request.POST), instance=payments)

        if form.is_valid() and payment_form.is_valid():

            with transaction.atomic():
                form.save()

                payment_form.instance.report = report
                payment_form.save()

            messages.success(request, "Walk-ins and payments updated successfully!")

            return redirect("admin_walkins_history")

    else:

        form = WalkinServicesForm(instance=walkins)
        payment_form = PaymentSummaryForm(instance=payments)

    return render(
        request,
        "admin_panel/my_reports/edit_walkins.html",
        {
            "form": form,
            "payment_form": payment_form,
            "report": report,
            "walkins": walkins,
        },
    )


@my_reports_required
def edit_revenue(request, report_id):
    report = _my_report(request, report_id)

    revenue = get_object_or_404(Revenue, report=report)

    if report.status == DailyReport.APPROVED:
        messages.error(request, "This report has already been approved and cannot be edited.")
        return redirect("admin_revenue_history")

    if request.method == "POST":

        form = RevenueBreakdownForm(request.POST, instance=revenue)

        if form.is_valid():
            form.save()

            messages.success(request, "Revenue updated successfully!")

            return redirect("admin_revenue_history")

    else:

        form = RevenueBreakdownForm(instance=revenue)

    return render(
        request,
        "admin_panel/my_reports/edit_revenue.html",
        {
            "form": form,
            "report": report,
            "revenue": revenue,
        },
    )


@my_reports_required
def edit_expenses(request, report_id):
    report = _my_report(request, report_id)

    if report.status == DailyReport.APPROVED:
        messages.error(request, "This report has already been approved and cannot be edited.")
        return redirect("admin_expenses_history")

    if request.method == "POST":

        form = ExpenseFormSet(request.POST, instance=report)

        if form.is_valid():

            form.save()

            messages.success(request, "Expense details updated successfully!")

            return redirect("admin_expenses_history")

    else:

        form = ExpenseFormSet(instance=report)

    return render(
        request,
        "admin_panel/my_reports/edit_expenses.html",
        {
            "form": form,
            "report": report,
        },
    )
