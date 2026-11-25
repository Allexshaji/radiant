"""The numbers on the Massage Package dashboard, worked out from the saved packages.

Same figures as the DASHBOARD sheet: overview, money, package-wise sales,
follow-up lists, and packages sold and expired per month and per year.
"""
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from .models import EXPIRING_DAYS, CustomerPackage, PackageType, add_months


def packages_for(customers):
    """Every package of these customers, with what the numbers need already loaded."""
    return list(
        CustomerPackage.objects.filter(customer__in=customers)
        .select_related("customer", "customer__branch", "package_type", "renewal")
        .prefetch_related("visits")
    )


def dashboard(customers):
    today = timezone.localdate()
    packages = packages_for(customers)
    status = {p.pk: p.status for p in packages}

    current = [p for p in packages if status[p.pk] in (CustomerPackage.ACTIVE, CustomerPackage.RENEWAL_DUE)]
    expired = [p for p in packages if status[p.pk] == CustomerPackage.EXPIRED]
    renewals = [p for p in packages if p.renewed_from_id]
    renewed_count = sum(1 for p in packages if status[p.pk] == CustomerPackage.RENEWED)

    overview = {
        "customers": customers.count(),
        "active_packages": len(current),
        "massages_remaining": sum(p.massages_remaining for p in current),
        "renewal_due": sum(1 for p in current if status[p.pk] == CustomerPackage.RENEWAL_DUE),
        "expiring_soon": sum(1 for p in current if 0 <= p.days_to_expiry <= EXPIRING_DAYS),
        "expired_not_renewed": len(expired),
        "renewed_customers": len({p.customer_id for p in renewals}),
    }

    money = {
        "sales": sum((p.rate for p in packages), Decimal("0")),
        "collected": sum((p.amount_paid for p in packages), Decimal("0")),
        "pending": sum((p.balance for p in packages), Decimal("0")),
    }

    # Package-wise sales, one row per package type in the rate list (plus any sold type no longer listed).
    by_type = defaultdict(lambda: {"customers": set(), "sales": Decimal("0"), "count": 0})
    for p in packages:
        row = by_type[p.package_type_id]
        row["customers"].add(p.customer_id)
        row["sales"] += p.rate
        row["count"] += 1
    package_rows = []
    listed = PackageType.objects.filter(Q(pk__in=by_type.keys()) | Q(is_active=True)).order_by("total_massages", "name")
    for package_type in listed:
        row = by_type.get(package_type.pk, {"customers": set(), "sales": Decimal("0"), "count": 0})
        package_rows.append({
            "name": package_type.name,
            "customers": len(row["customers"]),
            "sold": row["count"],
            "rate": package_type.rate,
            "sales": row["sales"],
        })
    best = max(package_rows, key=lambda r: r["sold"], default=None)

    # Of the packages that have ended (renewed, or expired without renewal), the share that was renewed.
    ended = renewed_count + len(expired)
    renewal_rate = round(renewed_count * 100 / ended, 1) if ended else None

    follow_ups_today = sorted(
        (p for p in packages if p.next_follow_up and p.next_follow_up <= today
         and status[p.pk] != CustomerPackage.RENEWED),
        key=lambda p: (p.next_follow_up, p.customer.name),
    )
    expired_list = sorted(expired, key=lambda p: p.expiry_date, reverse=True)

    return {
        "overview": overview,
        "money": money,
        "package_rows": package_rows,
        "package_total": {
            "customers": len({p.customer_id for p in packages}),
            "sold": len(packages),
            "sales": money["sales"],
        },
        "best_package": best["name"] if best and best["sold"] else None,
        "renewal_rate": renewal_rate,
        "follow_ups_today": follow_ups_today,
        "expired_list": expired_list,
        "months": _by_month(packages, today),
        "years": _by_year(packages, today),
        "today": today,
    }


def _by_month(packages, today):
    """Packages sold and expired in each of the last 12 months, oldest first."""
    sold = Counter((p.purchase_date.year, p.purchase_date.month) for p in packages)
    gone = Counter((p.expiry_date.year, p.expiry_date.month) for p in packages if p.expiry_date <= today)
    first = add_months(date(today.year, today.month, 1), -11)
    rows = []
    for i in range(12):
        month = add_months(first, i)
        key = (month.year, month.month)
        rows.append({"month": month, "sold": sold[key], "expired": gone[key]})
    return rows


def _by_year(packages, today):
    """Packages sold and expired in each of the last 5 years, oldest first."""
    sold = Counter(p.purchase_date.year for p in packages)
    gone = Counter(p.expiry_date.year for p in packages if p.expiry_date <= today)
    return [{"year": y, "sold": sold[y], "expired": gone[y]} for y in range(today.year - 4, today.year + 1)]


def follow_up_list(customers):
    """The Renewal Follow-up call list: packages that need a call, most urgent first."""
    rows = [p for p in packages_for(customers) if p.follow_up_priority is not None]
    return sorted(rows, key=lambda p: (p.follow_up_priority, p.expiry_date, p.customer.name))
