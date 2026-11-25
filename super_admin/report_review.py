"""The Super Admin's review of admin and staff daily reports.

Choose an admin (or a staff member), see their reports, open one to edit it,
then approve or reject it. Editing uses the same report pages admins use
(admin_panel/my_reports.py), which let the Super Admin open any report.
"""
from django.contrib import messages
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
STATUSES = [
    ("", "All"),
    (DailyReport.SUBMITTED, "Submitted"),
    (DailyReport.APPROVED, "Approved"),
    (DailyReport.REJECTED, "Rejected"),
]


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

    reports = DailyReport.objects.none()
    if person:
        reports = (
            DailyReport.objects.filter(staff=person)
            .select_related("branch", "super_admin_submission")
            .order_by("-report_date", "-id")
        )
        if status:
            reports = reports.filter(status=status)

    return render(request, "super_admin/review_reports.html", {
        "kind": kind,
        "info": info,
        "people": people,
        "person": person,
        "status": status,
        "statuses": STATUSES,
        "reports": reports,
    })


@super_admin_required
@require_POST
def set_report_status(request, report_id):
    """Approve or reject one admin or staff report. A rejection reason is kept on a sent report."""
    report = get_object_or_404(DailyReport.objects.select_related("staff"), id=report_id)
    action = request.POST.get("action")
    note = request.POST.get("note", "").strip()
    kind = "admin" if report.staff.role == User.ADMIN else "staff"
    back = f"{reverse(f'super_{kind}_reports')}?person={report.staff_id}"
    if request.POST.get("status"):
        back += f"&status={request.POST['status']}"

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
