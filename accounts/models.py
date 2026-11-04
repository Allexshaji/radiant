from django.contrib.auth.models import AbstractUser
from django.db import models


class Branch(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class User(AbstractUser):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    STAFF = "STAFF"

    ROLE_CHOICES = [
        (SUPER_ADMIN, "Super Admin"),
        (ADMIN, "Admin"),
        (STAFF, "Staff"),
    ]

    full_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(unique=True)
    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=STAFF)
    is_approved = models.BooleanField(default=False)
    monthly_salary = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Monthly salary set by the admin',
    )
    allowance = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Salary allowance added to the monthly total. Empty means no allowance (hidden from staff).',
    )
    blocked_sections = models.JSONField(
        default=list,
        blank=True,
        help_text='Admin areas this admin cannot open. Super Admins are not affected.',
    )

    def __str__(self):
        return self.full_name or self.username


class StaffFeatureSetting(models.Model):
    """On/off switch for one staff feature. No row means the feature is on."""

    key = models.CharField(max_length=50, unique=True)
    is_enabled = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.key}: {'on' if self.is_enabled else 'off'}"
