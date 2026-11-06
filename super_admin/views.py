from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.access import ADMIN_ROLES, ADMIN_SECTIONS, STAFF_FEATURES, is_super_admin, staff_feature_states
from accounts.models import Branch, StaffFeatureSetting, User
from admin_panel.models import ReportSubmission
from staff_panel.models import DailyReport

from .forms import AdminAccountForm


def _money_totals(reports):
    """Adds up the money on these daily reports, the same way the admin dashboard does."""
    totals = {
        "revenue": Decimal("0.00"),
        "payments": Decimal("0.00"),
        "expenses": Decimal("0.00"),
        "walkins": 0,
        "reports": 0,
    }
    for report in reports:
        totals["revenue"] += report.total_revenue or Decimal("0.00")
        totals["payments"] += report.total_payments or Decimal("0.00")
        totals["expenses"] += report.total_expenses or Decimal("0.00")
        totals["walkins"] += report.total_walkins or 0
        totals["reports"] += 1
    totals["net"] = totals["revenue"] - totals["expenses"]
    return totals


def super_admin_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not is_super_admin(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return login_required(wrapper)


def _is_last_active_super_admin(account):
    """True when this account is the only active Super Admin left. It must not be switched off, deleted or demoted."""
    if account.role != User.SUPER_ADMIN or not account.is_active:
        return False
    return not User.objects.filter(role=User.SUPER_ADMIN, is_active=True).exclude(pk=account.pk).exists()


def _access_summary(account):
    if account.role == User.SUPER_ADMIN:
        return "Full access"
    turned_off = len(account.blocked_sections or [])
    if turned_off == 0:
        return "All admin areas"
    return f"{len(ADMIN_SECTIONS) - turned_off} of {len(ADMIN_SECTIONS)} areas"


def _section_rows(selected):
    return [
        {"key": key, "label": label, "help": text, "checked": key in selected}
        for key, label, text in ADMIN_SECTIONS
    ]


@super_admin_required
def super_dashboard(request):
    admins = User.objects.filter(role=User.ADMIN)
    states = staff_feature_states()

    # Branch filter: an empty value means every branch. An unknown value falls back to every branch.
    branches = list(Branch.objects.order_by("name"))
    selected = request.GET.get("branch", "")
    if selected not in {str(branch.pk) for branch in branches}:
        selected = ""
    selected_branch = next((branch for branch in branches if str(branch.pk) == selected), None)

    all_reports = DailyReport.objects.all()
    if selected_branch:
        money = _money_totals(all_reports.filter(staff__branch=selected_branch))
        breakdown = []
    else:
        money = _money_totals(all_reports)
        # One row per branch, plus reports of staff who have no branch, so the rows add up to the total.
        breakdown = [
            {"name": branch.name, **_money_totals(all_reports.filter(staff__branch=branch))}
            for branch in branches
        ]
        unassigned = _money_totals(all_reports.filter(staff__branch__isnull=True))
        if unassigned["reports"]:
            breakdown.append({"name": "No branch", **unassigned})

    context = {
        "branches": branches,
        "selected": selected,
        "scope_label": selected_branch.name if selected_branch else "All branches",
        "money": money,
        "breakdown": breakdown,
        "admin_count": admins.count(),
        "active_admin_count": admins.filter(is_active=True).count(),
        "super_admin_count": User.objects.filter(role=User.SUPER_ADMIN, is_active=True).count(),
        "restricted_admin_count": sum(1 for account in admins if account.blocked_sections),
        "staff_count": User.objects.filter(role=User.STAFF, is_approved=True).count(),
        "pending_count": User.objects.filter(role=User.STAFF, is_approved=False).count(),
        "branch_count": Branch.objects.count(),
        "features": [
            {"label": label, "text": text, "enabled": states[key]}
            for key, label, text in STAFF_FEATURES
        ],
        "features_on": sum(1 for value in states.values() if value),
        "features_total": len(STAFF_FEATURES),
    }
    return render(request, "super_admin/dashboard.html", context)


@super_admin_required
def super_admin_list(request):
    accounts = User.objects.filter(role__in=ADMIN_ROLES).order_by("-role", "id")
    rows = [
        {
            "account": account,
            "is_self": account.pk == request.user.pk,
            "access": _access_summary(account),
        }
        for account in accounts
    ]
    return render(request, "super_admin/admins_list.html", {"rows": rows})


@super_admin_required
def super_admin_create(request):
    form = AdminAccountForm(request.POST or None, editing=False)

    if request.method == "POST" and form.is_valid():
        account = form.save(selected_sections=request.POST.getlist("sections"))
        messages.success(request, f"Account '{account.username}' was created.")
        return redirect("super_admin_list")

    if request.method == "POST":
        selected = set(request.POST.getlist("sections"))
    else:
        selected = {key for key, _label, _text in ADMIN_SECTIONS}

    return render(request, "super_admin/admin_form.html", {
        "form": form,
        "account": None,
        "is_self": False,
        "sections": _section_rows(selected),
    })


@super_admin_required
def super_admin_edit(request, user_id):
    account = get_object_or_404(User, pk=user_id, role__in=ADMIN_ROLES)
    is_self = account.pk == request.user.pk
    # Read before the form changes the account in memory during validation.
    original_role = account.role
    was_last_super = _is_last_active_super_admin(account)

    form = AdminAccountForm(request.POST or None, instance=account, editing=True, is_self=is_self)

    if request.method == "POST" and form.is_valid():
        demoting = original_role == User.SUPER_ADMIN and form.cleaned_data["role"] != User.SUPER_ADMIN
        if demoting and was_last_super:
            form.add_error("role", "At least one active Super Admin must remain.")
        else:
            password_changed = bool(form.cleaned_data.get("password"))
            account = form.save(selected_sections=request.POST.getlist("sections"))
            if is_self and password_changed:
                # Keeps the Super Admin signed in after changing their own password.
                update_session_auth_hash(request, account)
            messages.success(request, f"Account '{account.username}' was updated.")
            return redirect("super_admin_list")

    if request.method == "POST":
        selected = set(request.POST.getlist("sections"))
    else:
        selected = {key for key, _label, _text in ADMIN_SECTIONS if key not in (account.blocked_sections or [])}

    return render(request, "super_admin/admin_form.html", {
        "form": form,
        "account": account,
        "is_self": is_self,
        "sections": _section_rows(selected),
    })


@super_admin_required
@require_POST
def super_admin_toggle_active(request, user_id):
    account = get_object_or_404(User, pk=user_id, role__in=ADMIN_ROLES)

    if account.pk == request.user.pk:
        messages.error(request, "You cannot switch off your own account.")
    elif account.is_active and _is_last_active_super_admin(account):
        messages.error(request, "At least one active Super Admin must remain.")
    else:
        account.is_active = not account.is_active
        account.save(update_fields=["is_active"])
        state = "active" if account.is_active else "switched off"
        messages.success(request, f"Account '{account.username}' is now {state}.")
    return redirect("super_admin_list")


@super_admin_required
@require_POST
def super_admin_delete(request, user_id):
    account = get_object_or_404(User, pk=user_id, role__in=ADMIN_ROLES)

    if account.pk == request.user.pk:
        messages.error(request, "You cannot delete your own account.")
    elif _is_last_active_super_admin(account):
        messages.error(request, "At least one active Super Admin must remain.")
    else:
        username = account.username
        try:
            account.delete()
        except ProtectedError:
            messages.error(request, "This account has saved records, so it cannot be deleted. Switch it off instead.")
        else:
            messages.success(request, f"Account '{username}' was deleted.")
    return redirect("super_admin_list")


@super_admin_required
def staff_control(request):
    if request.method == "POST":
        chosen = set(request.POST.getlist("features"))
        for key, _label, _text in STAFF_FEATURES:
            StaffFeatureSetting.objects.update_or_create(key=key, defaults={"is_enabled": key in chosen})
        messages.success(request, "Staff module settings were saved.")
        return redirect("super_staff_control")

    states = staff_feature_states()
    features = [
        {"key": key, "label": label, "text": text, "enabled": states[key]}
        for key, label, text in STAFF_FEATURES
    ]
    return render(request, "super_admin/staff_control.html", {
        "features": features,
        "staff_count": User.objects.filter(role=User.STAFF, is_approved=True).count(),
    })


@super_admin_required
def received_reports(request):
    """Daily reports that admins have sent to the Super Admin, grouped by branch."""
    submissions = ReportSubmission.objects.select_related(
        "report",
        "report__branch",
        "report__staff",
        "sent_by",
    ).order_by(
        "report__branch__name",
        "-report__report_date",
        "-sent_at",
    )

    groups = []
    by_branch = {}

    for submission in submissions:
        report = submission.report
        branch = report.branch

        group = by_branch.get(branch.id)
        if group is None:
            group = {
                "branch": branch,
                "items": [],
                "report_count": 0,
                "walkins": 0,
                "revenue": Decimal("0.00"),
                "payments": Decimal("0.00"),
                "expenses": Decimal("0.00"),
            }
            by_branch[branch.id] = group
            groups.append(group)

        item = {
            "submission": submission,
            "report": report,
            "walkins": report.total_walkins,
            "revenue": report.total_revenue,
            "payments": report.total_payments,
            "expenses": report.total_expenses,
        }
        group["items"].append(item)
        group["report_count"] += 1
        group["walkins"] += item["walkins"]
        group["revenue"] += item["revenue"]
        group["payments"] += item["payments"]
        group["expenses"] += item["expenses"]

    for group in groups:
        group["net"] = group["revenue"] - group["expenses"]

    return render(
        request,
        "super_admin/received_reports.html",
        {
            "groups": groups,
            "total_reports": sum(group["report_count"] for group in groups),
        },
    )


@super_admin_required
@require_POST
def review_report(request, submission_id):
    """Approve or reject a daily report that an admin sent.

    Approve sets the report to APPROVED: the admin can no longer change or delete it.
    Reject sets it to REJECTED and needs a reason, which the admin sees on the report.
    """
    submission = get_object_or_404(
        ReportSubmission.objects.select_related("report"),
        id=submission_id,
    )
    report = submission.report
    action = request.POST.get("action")
    note = request.POST.get("note", "").strip()

    if action == "approve":
        report.status = DailyReport.APPROVED
        submission.review_note = ""
        messages.success(request, f"Report #{report.id} approved.")
    elif action == "reject":
        if not note:
            messages.error(request, f"Write a reason before rejecting report #{report.id}.")
            return redirect("super_received_reports")
        report.status = DailyReport.REJECTED
        submission.review_note = note
        messages.success(request, f"Report #{report.id} rejected. The admin can fix it and send it again.")
    else:
        messages.error(request, "Unknown action.")
        return redirect("super_received_reports")

    submission.reviewed_at = timezone.now()
    with transaction.atomic():
        report.save(update_fields=["status", "updated_at"])
        submission.save(update_fields=["review_note", "reviewed_at"])

    return redirect("super_received_reports")

