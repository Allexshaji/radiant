"""Massage packages: the rate list, customers, the packages they buy, and each massage they take.

Admins and Super Admins use this (see packages/views.py). Every customer belongs to a branch.
An admin sees only their own branch; the Super Admin sees every branch.

Numbers such as massages used, balance and status are worked out from the saved rows,
so they can never drift out of step with the visits and payments.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from accounts.models import Branch

# A package is "Renewal Due" when this few massages are left, or when it ends within EXPIRING_DAYS.
RENEWAL_DUE_REMAINING = 3
EXPIRING_DAYS = 7


def add_months(start, months):
    """The same day `months` later. A day that does not exist (31 Feb) becomes the month's last day."""
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    for day in (start.day, 30, 29, 28):
        try:
            return date(year, month, day)
        except ValueError:
            continue


def package_end_date(start, validity_months):
    """The last day of a package that starts on `start` and runs `validity_months` full months.

    A 6-month package from 26 Nov 2026 ends on 25 May 2027. The Add Package form fills the same date
    in the browser (packages/templates/packages/_expiry_script.html), and it can be changed there.
    """
    return add_months(start, validity_months) - timedelta(days=1)


class PackageType(models.Model):
    """One line of the Package Rate Master, for example "10 Massage" at Rs. 13,000 for 6 months."""

    name = models.CharField(max_length=60, unique=True)
    total_massages = models.PositiveIntegerField()
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    validity_months = models.PositiveIntegerField(
        default=6, help_text="How long the package lasts. The expiry date is worked out from this.",
    )
    is_active = models.BooleanField(default=True, help_text="Only active packages can be sold.")

    class Meta:
        ordering = ["total_massages", "name"]

    def __str__(self):
        return self.name


class Customer(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="package_customers")
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    # Optional details, filled in on the Add Customer page.
    email = models.EmailField(blank=True)
    gender = models.CharField(
        max_length=1, blank=True, choices=[("M", "Male"), ("F", "Female"), ("O", "Other")],
    )
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.CharField(max_length=255, blank=True)
    notes = models.CharField(max_length=255, blank=True, help_text="Preferences, how they found us, and so on.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.phone})"

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today, born = timezone.localdate(), self.date_of_birth
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


class CustomerPackage(models.Model):
    """One package one customer bought. A renewal is a new package that points back to the old one."""

    NOT_CONTACTED = "NOT_CONTACTED"
    CONTACTED = "CONTACTED"
    FOLLOW_UP_LATER = "FOLLOW_UP_LATER"
    NOT_INTERESTED = "NOT_INTERESTED"
    FOLLOW_UP_CHOICES = [
        (NOT_CONTACTED, "Not Contacted"),
        (CONTACTED, "Contacted"),
        (FOLLOW_UP_LATER, "Follow-up Later"),
        (NOT_INTERESTED, "Not Interested"),
    ]

    # Status values, worked out by `status` below (not saved).
    ACTIVE = "Active"
    RENEWAL_DUE = "Renewal Due"
    EXPIRED = "Expired"
    RENEWED = "Renewed"

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="packages")
    package_type = models.ForeignKey(PackageType, on_delete=models.PROTECT, related_name="sales")
    # Copied from the package type when sold, so a later price change does not alter old sales.
    total_massages = models.PositiveIntegerField()
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    purchase_date = models.DateField()
    expiry_date = models.DateField()
    renewed_from = models.OneToOneField(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="renewal",
        help_text="The customer's previous package, when this one is a renewal.",
    )
    follow_up_status = models.CharField(max_length=20, choices=FOLLOW_UP_CHOICES, default=NOT_CONTACTED)
    next_follow_up = models.DateField(null=True, blank=True)
    remarks = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-purchase_date", "-id"]

    def __str__(self):
        return f"{self.customer.name} - {self.package_type.name}"

    # --- worked-out numbers ---------------------------------------------------------------

    @property
    def massages_used(self):
        # Uses the prefetched visits when the list page loaded them.
        return len(self.visits.all())

    @property
    def massages_remaining(self):
        return max(self.total_massages - self.massages_used, 0)

    @property
    def last_massage_date(self):
        dates = [v.visit_date for v in self.visits.all()]
        return max(dates) if dates else None

    @property
    def balance(self):
        return max(self.rate - self.amount_paid, Decimal("0"))

    @property
    def payment_status(self):
        if self.amount_paid <= 0:
            return "Unpaid"
        return "Paid" if self.amount_paid >= self.rate else "Partial"

    @property
    def days_to_expiry(self):
        return (self.expiry_date - timezone.localdate()).days

    @property
    def is_renewed(self):
        return hasattr(self, "renewal") and self.renewal is not None

    @property
    def status(self):
        if self.is_renewed:
            return self.RENEWED
        if self.days_to_expiry < 0:
            return self.EXPIRED
        if self.massages_remaining <= RENEWAL_DUE_REMAINING or self.days_to_expiry <= EXPIRING_DAYS:
            return self.RENEWAL_DUE
        return self.ACTIVE

    @property
    def follow_up_priority(self):
        """1 = most urgent. Same order as the sheet's Renewal Follow-up list. None = no follow-up needed."""
        status = self.status
        if status == self.RENEWED or self.follow_up_status == self.NOT_INTERESTED:
            return None
        if status == self.EXPIRED:
            return 1
        remaining = self.massages_remaining
        if remaining <= RENEWAL_DUE_REMAINING:
            return 1 + max(remaining, 1)  # 0 or 1 left -> 2, 2 left -> 3, 3 left -> 4
        if 0 <= self.days_to_expiry <= EXPIRING_DAYS:
            return 5
        return None

    @property
    def follow_up_reason(self):
        priority = self.follow_up_priority
        if priority is None:
            return ""
        if priority == 1:
            return "Expired - Not Renewed"
        if priority == 5:
            return f"Expires in {self.days_to_expiry} day{'s' if self.days_to_expiry != 1 else ''}"
        left = self.massages_remaining
        return f"{left} Massage{'s' if left != 1 else ''} Remaining"


class MassageVisit(models.Model):
    """One massage taken from a package."""

    package = models.ForeignKey(CustomerPackage, on_delete=models.CASCADE, related_name="visits")
    visit_date = models.DateField()
    note = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-visit_date", "-id"]

    def __str__(self):
        return f"{self.package} on {self.visit_date}"
