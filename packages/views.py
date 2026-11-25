"""Massage package pages, for Admins and the Super Admin only.

An admin works with their own branch's customers. The Super Admin sees every branch
and can narrow any page to one branch with ?branch=<id>. Staff cannot open these pages.
Only the Super Admin can change the package rate list.
"""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.access import is_super_admin
from accounts.models import Branch, User

from . import stats
from .forms import FollowUpForm, PackageEditForm, PackageSaleForm, PackageTypeForm, VisitForm
from .models import Customer, CustomerPackage, MassageVisit, PackageType, add_months

STATUS_FILTERS = [
    ("", "All"),
    (CustomerPackage.ACTIVE, "Active"),
    (CustomerPackage.RENEWAL_DUE, "Renewal Due"),
    (CustomerPackage.EXPIRED, "Expired"),
    (CustomerPackage.RENEWED, "Renewed"),
]


def packages_required(view):
    """Admins (with a branch) and the Super Admin only."""
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        user = request.user
        if user.role not in (User.ADMIN, User.SUPER_ADMIN):
            raise PermissionDenied
        if user.role == User.ADMIN and not user.branch_id:
            messages.error(request, "Your account has no branch, so massage packages cannot be used.")
            return redirect("admin_dashboard")
        return view(request, *args, **kwargs)
    return wrapped


def _branch_filter(request):
    """(customers this user may see, chosen branch or None). Only the Super Admin can choose a branch."""
    if not is_super_admin(request.user):
        return Customer.objects.filter(branch_id=request.user.branch_id), None
    raw = request.GET.get("branch", "")
    branch = Branch.objects.filter(pk=int(raw)).first() if raw.isdigit() else None
    customers = Customer.objects.all()
    return (customers.filter(branch=branch) if branch else customers), branch


def _common(request, branch):
    return {
        "is_super": is_super_admin(request.user),
        "branches": Branch.objects.order_by("name") if is_super_admin(request.user) else None,
        "selected_branch": branch,
        "branch_query": f"branch={branch.pk}" if branch else "",
    }


def _package(request, pk):
    """A package this user may open: their branch's, or any for the Super Admin. Others are 404."""
    rows = CustomerPackage.objects.select_related("customer", "customer__branch", "package_type")
    if not is_super_admin(request.user):
        rows = rows.filter(customer__branch_id=request.user.branch_id)
    return get_object_or_404(rows, pk=pk)


# --- dashboard and lists ----------------------------------------------------------------------

@packages_required
def dashboard(request):
    customers, branch = _branch_filter(request)
    context = {**_common(request, branch), **stats.dashboard(customers)}
    return render(request, "packages/dashboard.html", context)


@packages_required
def package_list(request):
    customers, branch = _branch_filter(request)
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    if status not in dict(STATUS_FILTERS):
        status = ""

    if query:
        customers = customers.filter(Q(name__icontains=query) | Q(phone__icontains=query))
    rows = stats.packages_for(customers)
    if status:
        rows = [p for p in rows if p.status == status]
    rows.sort(key=lambda p: (p.purchase_date, p.pk), reverse=True)

    return render(request, "packages/package_list.html", {
        **_common(request, branch),
        "rows": rows,
        "query": query,
        "status": status,
        "status_filters": STATUS_FILTERS,
    })


@packages_required
def follow_ups(request):
    customers, branch = _branch_filter(request)
    return render(request, "packages/follow_ups.html", {
        **_common(request, branch),
        "rows": stats.follow_up_list(customers),
        "follow_up_choices": CustomerPackage.FOLLOW_UP_CHOICES,
    })


@packages_required
def renewal_history(request):
    customers, branch = _branch_filter(request)
    rows = (
        CustomerPackage.objects.filter(customer__in=customers, renewed_from__isnull=False)
        .select_related("customer", "customer__branch", "package_type", "renewed_from", "renewed_from__package_type")
        .order_by("-purchase_date", "-id")
    )
    return render(request, "packages/renewal_history.html", {**_common(request, branch), "rows": rows})


# --- selling, renewing, editing ---------------------------------------------------------------

def _sell(request, form, previous=None):
    """Save a sale from a valid form. Returns the new package."""
    data = form.cleaned_data
    if previous is not None:
        branch = previous.customer.branch
    elif is_super_admin(request.user):
        branch = data["branch"]
    else:
        branch = request.user.branch

    package_type = data["package_type"]
    with transaction.atomic():
        if previous is not None:
            customer = previous.customer
            customer.name, customer.phone = data["customer_name"], data["phone"]
            customer.save(update_fields=["name", "phone"])
        else:
            # Same phone in the same branch = the same customer.
            customer = Customer.objects.filter(branch=branch, phone=data["phone"]).first()
            if customer is None:
                customer = Customer.objects.create(branch=branch, name=data["customer_name"], phone=data["phone"])
        return CustomerPackage.objects.create(
            customer=customer,
            package_type=package_type,
            total_massages=package_type.total_massages,
            rate=data["rate"] if data.get("rate") is not None else package_type.rate,
            amount_paid=data["amount_paid"],
            purchase_date=data["purchase_date"],
            expiry_date=data.get("expiry_date") or add_months(data["purchase_date"], package_type.validity_months),
            renewed_from=previous,
            remarks=data.get("remarks", ""),
            created_by=request.user,
        )


@packages_required
def package_add(request):
    choose_branch = is_super_admin(request.user)
    form = PackageSaleForm(request.POST or None, choose_branch=choose_branch)
    if request.method == "POST" and form.is_valid():
        package = _sell(request, form)
        messages.success(request, f"{package.package_type.name} added for {package.customer.name}.")
        return redirect("package_detail", pk=package.pk)
    return render(request, "packages/package_form.html", {
        "form": form, "title": "Add Package", "rate_list": PackageType.objects.filter(is_active=True),
    })


@packages_required
def package_renew(request, pk):
    previous = _package(request, pk)
    if previous.is_renewed:
        messages.error(request, "This package has already been renewed.")
        return redirect("package_detail", pk=previous.renewal.pk)
    initial = {
        "customer_name": previous.customer.name,
        "phone": previous.customer.phone,
        "package_type": previous.package_type if previous.package_type.is_active else None,
    }
    form = PackageSaleForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        package = _sell(request, form, previous=previous)
        messages.success(request, f"{package.customer.name} renewed with {package.package_type.name}.")
        return redirect("package_detail", pk=package.pk)
    return render(request, "packages/package_form.html", {
        "form": form, "title": f"Renew Package - {previous.customer.name}", "previous": previous,
        "rate_list": PackageType.objects.filter(is_active=True),
    })


@packages_required
def package_detail(request, pk):
    package = _package(request, pk)
    return render(request, "packages/package_detail.html", {
        "package": package,
        "visits": package.visits.select_related("recorded_by"),
        "visit_form": VisitForm(),
        "follow_up_form": FollowUpForm(instance=package),
        "history": _customer_history(package.customer),
    })


def _customer_history(customer):
    return customer.packages.select_related("package_type", "renewal").prefetch_related("visits")


@packages_required
def package_edit(request, pk):
    package = _package(request, pk)
    form = PackageEditForm(request.POST or None, instance=package)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
            customer = package.customer
            customer.name, customer.phone = form.cleaned_data["customer_name"], form.cleaned_data["phone"]
            customer.save(update_fields=["name", "phone"])
        messages.success(request, "Package updated.")
        return redirect("package_detail", pk=package.pk)
    return render(request, "packages/package_edit.html", {"form": form, "package": package})


@packages_required
@require_POST
def package_delete(request, pk):
    package = _package(request, pk)
    customer, name = package.customer, package.customer.name
    with transaction.atomic():
        package.delete()
        if not customer.packages.exists():
            customer.delete()
    messages.success(request, f"Package of {name} deleted.")
    return redirect("package_list")


# --- visits and follow-up ---------------------------------------------------------------------

@packages_required
@require_POST
def visit_add(request, pk):
    package = _package(request, pk)
    form = VisitForm(request.POST)
    if package.massages_remaining <= 0:
        messages.error(request, "No massages left in this package. Renew it to add more.")
    elif not form.is_valid():
        messages.error(request, " ".join(e for errors in form.errors.values() for e in errors))
    else:
        visit = form.save(commit=False)
        visit.package, visit.recorded_by = package, request.user
        visit.save()
        messages.success(request, f"Massage recorded. {package.massages_remaining} left.")
    return redirect("package_detail", pk=package.pk)


@packages_required
@require_POST
def visit_delete(request, pk, visit_id):
    package = _package(request, pk)
    get_object_or_404(MassageVisit, pk=visit_id, package=package).delete()
    messages.success(request, "Massage entry removed.")
    return redirect("package_detail", pk=package.pk)


@packages_required
@require_POST
def follow_up_update(request, pk):
    package = _package(request, pk)
    form = FollowUpForm(request.POST, instance=package)
    if form.is_valid():
        form.save()
        messages.success(request, f"Follow-up saved for {package.customer.name}.")
    else:
        messages.error(request, "Could not save the follow-up. Check the date.")
    back = request.POST.get("next", "")
    if back.startswith("/") and not back.startswith("//"):
        return redirect(back)
    return redirect("package_detail", pk=package.pk)


# --- rate list ----------------------------------------------------------------------------------

@packages_required
def rates(request):
    """Everyone here can see the rates. Only the Super Admin can add or change them."""
    can_edit = is_super_admin(request.user)
    edit_id = request.GET.get("edit", "")
    editing = PackageType.objects.filter(pk=int(edit_id)).first() if edit_id.isdigit() and can_edit else None

    form = None
    if can_edit:
        form = PackageTypeForm(request.POST or None, instance=editing)
        if request.method == "POST":
            if form.is_valid():
                saved = form.save()
                messages.success(request, f"{saved.name} saved.")
                return redirect("package_rates")
    elif request.method == "POST":
        raise PermissionDenied

    return render(request, "packages/rates.html", {
        "rates": PackageType.objects.all(),
        "form": form,
        "editing": editing,
        "can_edit": can_edit,
    })

