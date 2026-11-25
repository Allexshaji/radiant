"""The Super Admin's review of admin and staff daily reports.

Choose an admin (or a staff member), see their reports, open one to edit it,
then approve or reject it. Editing uses the same report pages admins use
(admin_panel/my_reports.py), which let the Super Admin open any report.
"""
from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User
from admin_panel.models import ReportSubmission
from staff_panel.models import DailyReport

from .views import super_admin_required

KINDS = {
    "admin": {"role": User.ADMIN, "title": "Admin Reports", "who": "admin"},
    "staff": {"role": User.STAFF, "title": "Staff Reports", "who": "staff member"},
}
PAGE_SIZE = 30
STATUSES = [
    ("", "All"),
    (DailyReport.SUBMITTED, "Submitted"),
    (DailyReport.APPROVED, "Approved"),
    (DailyReport.REJECTED, "Rejected"),
]


def _back_url(request, report):
    """The review list the form came from, with the same person and status filters."""
    kind = "admin" if report.staff.role == User.ADMIN else "staff"
    query = {k: request.POST[k] for k in ("person", "status") if request.POST.get(k)}
    url = reverse(f"super_{kind}_reports")
    return f"{url}?{urlencode(query)}" if query else url


def _kind(kind):
    if kind not in KINDS:
        raise Http404
    return KINDS[kind]


@super_admin_required
def review_reports(request, kind):
    info = _kind(kind)
    people = (
        User.objects.filter(role=info["role"])
        .select_related("branch")
        .order_by("branch__name", "first_name", "username")
    )

    person_id = request.GET.get("person", "")
    person = people.filter(pk=int(person_id)).first() if person_id.isdigit() else None
    status = request.GET.get("status", "")
    if status not in dict(STATUSES):
        status = ""

    # All reports of admins (or of staff) show at once. Choosing a person or a status narrows the list.
    reports = (
        DailyReport.objects.filter(staff__role=info["role"])
        .select_related("branch", "staff", "super_admin_submission")
        .order_by("-report_date", "-id")
    )
    if person:
        reports = reports.filter(staff=person)
    if status:
        reports = reports.filter(status=status)
    page = Paginator(reports, PAGE_SIZE).get_page(request.GET.get("page"))

    return render(request, "super_admin/review_reports.html", {
        "kind": kind,
        "info": info,
        "people": people,
        "person": person,
        "status": status,
        "statuses": STATUSES,
        "reports": page,
        "page": page,
    })


@super_admin_required
@require_POST
def set_report_status(request, report_id):
    """Approve or reject one admin or staff report. A rejection reason is kept on a sent report."""
    report = get_object_or_404(DailyReport.objects.select_related("staff"), id=report_id)
    action = request.POST.get("action")
    note = request.POST.get("note", "").strip()
    back = _back_url(request, report)

    if action == "approve":
        report.status = DailyReport.APPROVED
        note = ""
        done = f"Report #{report.id} approved."
    elif action == "reject":
        report.status = DailyReport.REJECTED
        done = f"Report #{report.id} rejected."
    else:
        messages.error(request, "Unknown action.")
        return redirect(back)

    submission = ReportSubmission.objects.filter(report=report).first()
    with transaction.atomic():
        report.save(update_fields=["status", "updated_at"])
        if submission:
            # Same record "Received Reports" uses, so both pages agree.
            submission.review_note = note
            submission.reviewed_at = timezone.now()
            submission.save(update_fields=["review_note", "reviewed_at"])

    messages.success(request, done)
    return redirect(back)


@super_admin_required
@require_POST
def delete_report(request, report_id):
    """Delete an admin or staff report, with everything in it (walk-ins, payments, revenue, expenses)."""
    report = get_object_or_404(DailyReport.objects.select_related("staff"), id=report_id)
    back = _back_url(request, report)
    owner = report.staff.get_full_name() or report.staff.username
    number = report.id
    report.delete()
    messages.success(request, f"Report #{number} of {owner} deleted.")
    return redirect(back)
