"""Monthly salary and leave deductions.

- Each staff member has a monthly salary, entered by the admin.
- Per day = monthly salary divided by the number of days in that month.
- Only paid leave (the built-in Paid Leave) is not deducted.
- Sick leave is never paid, so each sick day is deducted at the per-day amount.
- Any other approved leave (casual, LOP and so on) is deducted at the per-day amount.
- Only Monday to Saturday leave days are deducted.
- Every approved leave in the month counts, including days that are still to come.
- A day that has both paid leave and another leave is not deducted.
"""
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from accounts.models import User
from staff_panel.models import LeaveApplication

TWO_PLACES = Decimal("0.01")


def is_sick_leave(leave_type):
    return "sick" in leave_type.name.lower()


def is_paid_leave(leave_type):
    """Only paid leave types are not deducted. Sick leave is never paid, whatever its tick box says."""
    return leave_type.is_paid and not is_sick_leave(leave_type)


def parse_month(raw):
    """Turn 'YYYY-MM' into the first day of that month. Returns None if it is not a month."""
    try:
        year, month = (int(part) for part in str(raw).split("-")[:2])
        return date(year, month, 1)
    except (TypeError, ValueError):
        return None


def month_range(month_start):
    """First and last day of the month that contains month_start."""
    first = month_start.replace(day=1)
    if first.month == 12:
        next_first = date(first.year + 1, 1, 1)
    else:
        next_first = date(first.year, first.month + 1, 1)
    return first, next_first - timedelta(days=1)


def monthly_summary(staff, month_start):
    """Salary summary for one staff member for the month that contains month_start."""
    first, last = month_range(month_start)
    days_in_month = last.day
    counted_until = last  # all approved leave in the month, including days still to come

    salary = staff.monthly_salary
    has_salary = salary is not None
    monthly = Decimal(salary) if has_salary else Decimal("0")
    per_day = (monthly / days_in_month).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    # All approved leave days in the month (Monday to Saturday only).
    no_deduction_on = set()
    deducted_on = set()
    sick_on = set()
    if counted_until >= first:
        leaves = LeaveApplication.objects.filter(
            staff=staff,
            status="approved",
            start_date__lte=counted_until,
            end_date__gte=first,
        ).select_related("leave_type")
        for leave in leaves:
            day = max(leave.start_date, first)
            end = min(leave.end_date, counted_until)
            while day <= end:
                if day.weekday() < 6:
                    if is_paid_leave(leave.leave_type):
                        no_deduction_on.add(day)
                    else:
                        deducted_on.add(day)
                        if is_sick_leave(leave.leave_type):
                            sick_on.add(day)
                day += timedelta(days=1)
    deducted_on -= no_deduction_on  # a day with paid leave is never deducted
    sick_on -= no_deduction_on

    deducted_days = len(deducted_on)
    deduction = (monthly * deducted_days / days_in_month).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    # The allowance is added as it is. It is not reduced by leave.
    has_allowance = staff.allowance is not None
    allowance = Decimal(staff.allowance).quantize(TWO_PLACES, rounding=ROUND_HALF_UP) if has_allowance else Decimal("0")

    return {
        "month": first,
        "has_rate": has_salary,
        "monthly": monthly.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        "per_day": per_day,
        "deducted_days": deducted_days,
        "total_leave_days": deducted_days + len(no_deduction_on),
        "sick_days": len(sick_on),
        "no_deduction_days": len(no_deduction_on),
        "deduction": deduction,
        "has_allowance": has_allowance,
        "allowance": allowance.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        "total": (monthly - deduction + allowance).quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
    }


def staff_payroll_rows(month_start, members=None):
    """One row per approved staff member, with that month's summary. `members` limits the rows, e.g. to one branch."""
    if members is None:
        members = User.objects.filter(role=User.STAFF, is_approved=True)
    members = members.select_related("branch").order_by("full_name", "username")
    return [{**monthly_summary(member, month_start), "staff": member} for member in members]
