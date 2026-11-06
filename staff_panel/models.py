from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from accounts.models import Branch
from admin_panel.models import LeaveType


class Attendance(models.Model):
    PRESENT = "PRESENT"
    HALF_DAY = "HALF_DAY"
    LEAVE = "LEAVE"

    STATUS_CHOICES = [
        (PRESENT, "Present"),
        (HALF_DAY, "Half day"),
        (LEAVE, "Leave"),
    ]

    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    date = models.DateField(default=timezone.localdate)
    check_in = models.DateTimeField(null=True, blank=True)  # Changed: removed auto_now_add
    check_out = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=PRESENT,
    )
    created_at = models.DateTimeField(auto_now_add=True,null=True)

    class Meta:
        unique_together = ('staff', 'date', 'branch')

    def __str__(self):
        return f"{self.staff} - {self.date}"


class CheckInCheckOut(models.Model):
    ACTIVITY_CHOICES = [
        ('check_in', 'Check In'),
        ('check_out', 'Check Out'),
    ]
    
    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=10, choices=ACTIVITY_CHOICES)
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    # Where the staff member was when this check-in or check-out was recorded.
    # Empty when the browser did not share a location.
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    accuracy_m = models.FloatField(null=True, blank=True, help_text='Accuracy radius in metres, as reported by the device')
    # A short name for that place, looked up when the check-in is saved. Empty if it could not be found.
    place_name = models.CharField(max_length=255, blank=True, default='')
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        return f"{self.attendance.staff.username} - {self.activity_type} - {self.timestamp.strftime('%H:%M:%S')}"

class DailyReport(models.Model):

    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

    STATUS_CHOICES = [
        (SUBMITTED, "Submitted"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
    ]

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="daily_reports",
    )

    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="daily_reports",
    )

    report_date = models.DateField(
        default=timezone.localdate
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=SUBMITTED,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



    @property
    def total_walkins(self):
        w = getattr(self, "walkins", None)
        if w is None:
            return 0
        return w.total_walkins or 0

    @property
    def total_revenue(self):
        rev = getattr(self, "revenues", None)
        if rev is None:
            return Decimal("0.00")
        return rev.total_revenue or Decimal("0.00")

    @property
    def total_payments(self):
        p = getattr(self, "payments", None)
        if p is None:
            return Decimal("0.00")
        return p.total_payments or Decimal("0.00")

    @property
    def total_expenses(self):
        return (
            self.expenses.aggregate(
                total=Sum("amount")
            )["total"]
            or Decimal("0.00")
        )

    @property
    def net_amount(self):
        return self.total_revenue - self.total_expenses

    def __str__(self):
        return f"{self.branch} - {self.report_date}"


class WalkInService(models.Model):

    report = models.OneToOneField(
        DailyReport,
        on_delete=models.CASCADE,
        related_name="walkins",
    )

    total_walkins = models.PositiveIntegerField(
        default=0
    )

    treatment_count = models.PositiveIntegerField(
        default=0
    )

    package_count = models.PositiveIntegerField(
        default=0
    )

    normal_massage_count = models.PositiveIntegerField(
        default=0
    )

    consultation_count = models.PositiveIntegerField(
        default=0
    )

    sales_count = models.PositiveIntegerField(
        default=0
    )

    def __str__(self):
        return f"Walk-ins - {self.report.report_date}"


class Revenue(models.Model):

    report = models.OneToOneField(
        DailyReport,
        on_delete=models.CASCADE,
        related_name="revenues",
    )

    treatment_revenue = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    massage_revenue = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    new_package_revenue = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    consultation_revenue = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    sales_revenue = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    @property
    def total_revenue(self):
        return (
            self.treatment_revenue
            + self.massage_revenue
            + self.new_package_revenue
            + self.consultation_revenue
            + self.sales_revenue
        )

    def __str__(self):
        return f"Revenue - {self.report.report_date}"



class PaymentSummary(models.Model):

    report = models.OneToOneField(
        DailyReport,
        on_delete=models.CASCADE,
        related_name="payments",
    )

    cash = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    gpay = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    card = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    @property
    def total_payments(self):
        return (
            self.cash
            + self.gpay
            + self.card
        )

    def __str__(self):
        return f"Payments - {self.report.report_date}"



class ExpenseItem(models.Model):
    report = models.ForeignKey(
        DailyReport,
        on_delete=models.CASCADE,
        related_name="expenses",
        null=True,
        blank=True,
    )

    # The expense name chosen from the admin's list.
    description = models.CharField(max_length=255)

    # Optional details typed by staff, e.g. "Kitchen bulbs x 6".
    note = models.CharField(max_length=255, blank=True)

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.description







class LeaveApplication(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    # Staff member details
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='leave_applications'
    )
    
    # Leave details
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    
    # Status & Approval
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending'
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_leaves'
    )
    rejection_reason = models.TextField(blank=True)
    
    # Timestamps
    applied_date = models.DateTimeField(auto_now_add=True)
    decision_date = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-applied_date']
        verbose_name = 'Leave Application'
        verbose_name_plural = 'Leave Applications'
    
    @property
    def days_requested(self):
        return (self.end_date - self.start_date).days + 1
    
    @property
    def is_pending(self):
        return self.status == 'pending'
    
    @property
    def is_approved(self):
        return self.status == 'approved'
    
    def __str__(self):
        return f"{self.staff.username} - {self.leave_type.name} ({self.start_date})"


class Requirement(models.Model):
    """A requirement a staff member sends to the admin.

    A row exists only once it has been sent, so the admin never sees drafts.
    """

    PENDING = "PENDING"
    APPROVED = "APPROVED"

    STATUS_CHOICES = [
        (PENDING, "Waiting for approval"),
        (APPROVED, "Approved"),
    ]

    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="requirements",
    )
    text = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    sent_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_requirements",
    )

    class Meta:
        ordering = ["-sent_at"]

    @property
    def is_approved(self):
        return self.status == self.APPROVED

    def __str__(self):
        return f"{self.staff.username} - {self.text[:40]}"


 