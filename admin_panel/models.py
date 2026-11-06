from django.db import models

from django.conf import settings
from django.utils import timezone
from datetime import date
from dateutil.relativedelta import relativedelta
# Create your models here.


class LeaveType(models.Model):
    """Leave types available"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    days_per_year = models.IntegerField(default=10)
    is_active = models.BooleanField(default=True)
    is_paid = models.BooleanField(default=False, help_text='Paid leave is not deducted from salary')
    is_builtin = models.BooleanField(default=False, editable=False, help_text='Built-in leave types cannot be deleted')

    def save(self, *args, **kwargs):
        # The built-in Paid Leave type is always paid.
        if self.is_builtin:
            self.is_paid = True
        super().save(*args, **kwargs)
    created_at = models.DateTimeField(auto_now_add=True,null=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name



class ExpenseType(models.Model):
    """Expense names added by the admin. Staff pick from these when they enter expenses."""
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(
        default=True,
        help_text='Inactive expenses are hidden from the staff dropdown',
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Salary(models.Model):
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='salaries'
    )
    month = models.DateField(help_text="First day of the month")
    basic_salary = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Calculated fields
    working_days = models.IntegerField(default=0)
    leave_days = models.IntegerField(default=0)
    attended_days = models.IntegerField(default=0)
    
    # Salary breakdown
    per_day_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    leave_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Status
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_salaries'
    )
    approval_date = models.DateTimeField(null=True, blank=True)
    paid_date = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('staff', 'month')
        ordering = ['-month']
    
    def __str__(self):
        return f"{self.staff.username} - {self.month.strftime('%B %Y')}"
    
    def calculate_working_days(self):
        """Calculate working days in month (excluding weekends)"""
        start_date = self.month
        end_date = (start_date + relativedelta(months=1)) - relativedelta(days=1)
        
        working_days = 0
        current_date = start_date
        
        while current_date <= end_date:
            if current_date.weekday() < 6:  # Monday to Saturday
                working_days += 1
            current_date += relativedelta(days=1)
        
        return working_days
    
    def calculate_leave_days(self):
        """Get approved leave days in this month"""
        start_date = self.month
        end_date = (start_date + relativedelta(months=1)) - relativedelta(days=1)
        
        from staff_panel.models import LeaveApplication
        leaves = LeaveApplication.objects.filter(
            staff=self.staff,
            status='approved',
            start_date__lte=end_date,
            end_date__gte=start_date
        )
        
        leave_days = 0
        for leave in leaves:
            current_date = max(leave.start_date, start_date)
            leave_end = min(leave.end_date, end_date)
            
            while current_date <= leave_end:
                if current_date.weekday() < 6:  # Only count working days
                    leave_days += 1
                current_date += relativedelta(days=1)
        
        return leave_days
    
    def calculate_salary(self):
        """Calculate net salary based on leaves"""
        self.working_days = self.calculate_working_days()
        self.leave_days = self.calculate_leave_days()
        self.attended_days = self.working_days - self.leave_days
        
        self.per_day_salary = self.basic_salary / self.working_days if self.working_days > 0 else 0
        self.leave_deduction = self.per_day_salary * self.leave_days
        self.net_salary = self.basic_salary - self.leave_deduction
        
        self.save()
        return self.net_salary

class ReportSubmission(models.Model):
    """A daily report that an admin has sent to the Super Admin.

    One row per report. Sending the same report again only updates who sent it and when.
    The row goes away with the report, so a report that is deleted also leaves the inbox.
    """
    report = models.OneToOneField(
        'staff_panel.DailyReport',
        on_delete=models.CASCADE,
        related_name='super_admin_submission',
    )
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_report_submissions',
    )
    sent_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f"Report #{self.report_id} sent {self.sent_at:%d %b %Y}"
