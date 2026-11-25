"""The date a new daily report is for. Staff, admin and Super Admin pages all use this one rule."""
from datetime import date

from django.utils import timezone


def chosen_report_date(post):
    """Read the report date from a submitted form.

    Returns (date, None) when it is fine, or (None, message) when it is not.
    No date sent means today. A future date is refused.
    """
    raw = (post.get("report_date") or "").strip()
    today = timezone.localdate()
    if not raw:
        return today, None
    try:
        picked = date.fromisoformat(raw)
    except ValueError:
        return None, "Choose a valid date."
    if picked > today:
        return None, "A report cannot be made for a future date."
    return picked, None
