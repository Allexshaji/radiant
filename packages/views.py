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
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.access import is_super_admin
from accounts.models import Branch, User

from . import stats
from .forms import (
    CustomerForm, FollowUpForm, PackageDetailsForm, PackageEditForm, PackageSaleForm, PackageTypeForm,
    VisitForm,
)
from .models import Customer, CustomerPackage, MassageVisit, PackageType, package_end_date

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

def _create_package(request, customer, data, previous=None):
    """Save one package for `customer` from the cleaned package fields. Returns the new package."""
    package_type = data["package_type"]
    return CustomerPackage.objects.create(
        customer=customer,
        package_type=package_type,
        total_massages=package_type.total_massages,
        rate=data["rate"] if data.get("rate") is not None else package_type.rate,
        amount_paid=data["amount_paid"],
        purchase_date=data["purchase_date"],
        expiry_date=data.get("expiry_date") or package_end_date(data["purchase_date"], package_type.validity_months),
        renewed_from=previous,
        remarks=data.get("remarks", ""),
        created_by=request.user,
    )


def _sell(request, form, previous=None):
    """Save a sale from a valid PackageSaleForm (customer typed in). Returns the new package."""
    data = form.cleaned_data
    if previous is not None:
        branch = previous.customer.branch
    elif is_super_admin(request.user):
        branch = data["branch"]
    else:
        branch = request.user.branch

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
        return _create_package(request, customer, data, previous=previous)


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
    package.delete()
    messages.success(request, f"Package of {name} deleted.")
    # The customer and their details stay; only this package is removed.
    return redirect("customer_detail", pk=customer.pk)


# --- visits and follow-up ---------------------------------------------------------------------

def _back(request, package):
    """Go back to the page the form was on (a path on this site), else to the package page."""
    back = request.POST.get("next", "")
    if back.startswith("/") and not back.startswith("//"):
        return redirect(back)
    return redirect("package_detail", pk=package.pk)


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
        messages.success(request, f"Massage recorded for {package.customer.name}. {package.massages_remaining} left.")
    return _back(request, package)


@packages_required
@require_POST
def visit_undo(request, pk):
    """Take back the massage recorded last (for a wrong click). The massage goes back into the package."""
    package = _package(request, pk)
    last = package.visits.order_by("-created_at", "-id").first()
    if last is None:
        messages.error(request, "No massage to undo in this package.")
    else:
        day = last.visit_date
        last.delete()
        messages.success(
            request,
            f"Undone: the massage on {day:%d %b %Y} was removed. {package.massages_remaining} left.",
        )
    return _back(request, package)


@packages_required
@require_POST
def visit_delete(request, pk, visit_id):
    package = _package(request, pk)
    visit = get_object_or_404(MassageVisit, pk=visit_id, package=package)
    day = visit.visit_date
    visit.delete()
    messages.success(request, f"Massage on {day:%d %b %Y} removed. {package.massages_remaining} left.")
    return _back(request, package)


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
    return _back(request, package)


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



# --- customers ----------------------------------------------------------------------------------

def _customer(request, pk):
    """A customer this user may open: their branch's, or any for the Super Admin. Others are 404."""
    rows = Customer.objects.select_related("branch")
    if not is_super_admin(request.user):
        rows = rows.filter(branch_id=request.user.branch_id)
    return get_object_or_404(rows, pk=pk)


def _split_packages(customer):
    """(running packages, earlier packages) of a customer. Running = Active or Renewal Due."""
    running, earlier = [], []
    for p in stats.packages_for(Customer.objects.filter(pk=customer.pk)):
        (running if p.status in (CustomerPackage.ACTIVE, CustomerPackage.RENEWAL_DUE) else earlier).append(p)
    running.sort(key=lambda p: p.expiry_date)
    earlier.sort(key=lambda p: (p.purchase_date, p.pk), reverse=True)
    return running, earlier


@packages_required
def customer_list(request):
    customers, branch = _branch_filter(request)
    query = request.GET.get("q", "").strip()
    if query:
        customers = customers.filter(Q(name__icontains=query) | Q(phone__icontains=query))

    by_customer = {}
    for p in stats.packages_for(customers):
        by_customer.setdefault(p.customer_id, []).append(p)
    rows = []
    for customer in customers.select_related("branch").order_by("name"):
        packages = by_customer.get(customer.pk, [])
        running = [p for p in packages if p.status in (CustomerPackage.ACTIVE, CustomerPackage.RENEWAL_DUE)]
        visits = [p.last_massage_date for p in packages if p.last_massage_date]
        rows.append({
            "customer": customer,
            "running": running,
            "remaining": sum(p.massages_remaining for p in running),
            "packages": len(packages),
            "last_visit": max(visits) if visits else None,
            "balance": sum((p.balance for p in packages), 0),
        })

    return render(request, "packages/customer_list.html", {**_common(request, branch), "rows": rows, "query": query})


@packages_required
def customer_add(request):
    """Add a customer with their details and their first package, in one step."""
    choose_branch = is_super_admin(request.user)
    customer_form = CustomerForm(request.POST or None, choose_branch=choose_branch)
    package_form = PackageDetailsForm(request.POST or None, prefix="pkg")

    if request.method == "POST" and customer_form.is_valid() and package_form.is_valid():
        branch = customer_form.cleaned_data["branch"] if choose_branch else request.user.branch
        existing = Customer.objects.filter(branch=branch, phone=customer_form.cleaned_data["phone"]).first()
        if existing:
            customer_form.add_error(
                "phone", f"{existing.name} already has this phone number in {branch.name}. "
                         f"Open that customer to add a package.",
            )
            return render(request, "packages/customer_add.html", {
                "customer_form": customer_form, "package_form": package_form, "existing": existing,
                "rate_list": PackageType.objects.filter(is_active=True),
            })
        with transaction.atomic():
            customer = customer_form.save(commit=False)
            customer.branch = branch
            customer.save()
            package = _create_package(request, customer, package_form.cleaned_data)
        messages.success(request, f"{customer.name} added with {package.package_type.name}.")
        return redirect("customer_detail", pk=customer.pk)

    return render(request, "packages/customer_add.html", {
        "customer_form": customer_form, "package_form": package_form,
        "rate_list": PackageType.objects.filter(is_active=True),
    })


@packages_required
def customer_detail(request, pk):
    customer = _customer(request, pk)
    running, earlier = _split_packages(customer)
    every = sorted(running + earlier, key=lambda p: (p.purchase_date, p.pk), reverse=True)
    return render(request, "packages/customer_detail.html", {
        "customer": customer,
        "running": running,
        "earlier": earlier,
        # Every package this customer has taken, newest first, for "All Package History".
        "all_packages": every,
        "today": timezone.localdate(),
        "visit_form": VisitForm(),
        "total_paid": sum((p.amount_paid for p in running + earlier), 0),
        "total_due": sum((p.balance for p in running + earlier), 0),
    })


@packages_required
def customer_edit(request, pk):
    customer = _customer(request, pk)
    form = CustomerForm(request.POST or None, instance=customer)
    if request.method == "POST" and form.is_valid():
        clash = (Customer.objects.filter(branch=customer.branch, phone=form.cleaned_data["phone"])
                 .exclude(pk=customer.pk).first())
        if clash:
            form.add_error("phone", f"{clash.name} already has this phone number in {customer.branch.name}.")
        else:
            form.save()
            messages.success(request, "Customer details saved.")
            return redirect("customer_detail", pk=customer.pk)
    return render(request, "packages/customer_edit.html", {"form": form, "customer": customer})


@packages_required
def customer_package_add(request, pk):
    """Add another package for a customer who is already saved."""
    customer = _customer(request, pk)
    form = PackageDetailsForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        package = _create_package(request, customer, form.cleaned_data)
        messages.success(request, f"{package.package_type.name} added for {customer.name}.")
        return redirect("customer_detail", pk=customer.pk)
    return render(request, "packages/customer_package_add.html", {
        "form": form, "customer": customer, "rate_list": PackageType.objects.filter(is_active=True),
    })
