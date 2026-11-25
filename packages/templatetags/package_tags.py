from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def rs(value):
    """Rupees with Indian grouping and no paise: 123456.00 -> "Rs. 1,23,456"."""
    try:
        amount = int(Decimal(value).quantize(Decimal("1")))
    except (InvalidOperation, TypeError, ValueError):
        return "Rs. 0"
    sign, digits = ("-" if amount < 0 else ""), str(abs(amount))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups) + "," + tail
    return f"Rs. {sign}{digits}"


STATUS_STYLES = {
    "Active": "bg-emerald-50 text-emerald-700 border-emerald-100",
    "Renewal Due": "bg-amber-50 text-amber-700 border-amber-100",
    "Expired": "bg-rose-50 text-rose-700 border-rose-100",
    "Renewed": "bg-indigo-50 text-indigo-700 border-indigo-100",
}


@register.filter
def status_style(status):
    return STATUS_STYLES.get(status, "bg-gray-50 text-gray-700 border-gray-100")
