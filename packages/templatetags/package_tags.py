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


@register.simple_tag
def package_validity():
    """{package id: validity in months} for every package on sale, for the expiry-date script."""
    from packages.models import PackageType
    return {str(t.pk): t.validity_months for t in PackageType.objects.filter(is_active=True)}


def _whatsapp_number(phone):
    """An Indian phone number as WhatsApp wants it: country code and digits, no +. "" if it cannot be read."""
    digits = "".join(ch for ch in phone if ch.isdigit())
    if phone.strip().startswith("+"):
        return digits
    if len(digits) == 10:
        return "91" + digits
    if len(digits) == 11 and digits.startswith("0"):
        return "91" + digits[1:]
    if len(digits) == 12 and digits.startswith("91"):
        return digits
    return ""


@register.filter
def whatsapp_url(package):
    """A wa.me link that opens WhatsApp with a ready reminder for this package. Staff check it and press Send.

    The message is in Malayalam for the customer. Empty if the phone number cannot be used.
    """
    from urllib.parse import quote

    number = _whatsapp_number(package.customer.phone)
    if not number:
        return ""
    left = package.massages_remaining
    text = (
        f"നമസ്കാരം {package.customer.name}, Radiant Ayurveda {package.customer.branch.name}-ൽ നിന്നാണ്. "
        f"നിങ്ങളുടെ {package.package_type.name} പാക്കേജിൽ ഇനി {left} മസാജ് ബാക്കിയുണ്ട്. "
        f"പാക്കേജ് {package.expiry_date:%d-%m-%Y}-ന് അവസാനിക്കും. "
        f"അതിനു മുൻപ് മസാജ് ബുക്ക് ചെയ്യാൻ ഈ മെസ്സേജിന് മറുപടി നൽകുകയോ ഞങ്ങളെ വിളിക്കുകയോ ചെയ്യൂ. നന്ദി!"
    )
    return f"https://wa.me/{number}?text={quote(text)}"


@register.inclusion_tag("packages/_alert_banner.html", takes_context=True)
def package_alert_banner(context):
    """A banner for the main dashboards: how many customers have a package ending within a week with
    massages left. Shown to admins (their branch) and the Super Admin (every branch) who can use packages."""
    from accounts.access import is_super_admin
    from accounts.models import User
    from packages.models import Customer
    from packages.stats import expiry_alerts

    request = context.get("request")
    can = context.get("can")
    user = getattr(request, "user", None)
    if user is None or not getattr(can, "packages", False) or user.role not in (User.ADMIN, User.SUPER_ADMIN):
        return {"rows": []}
    if is_super_admin(user):
        customers = Customer.objects.all()
    elif user.branch_id:
        customers = Customer.objects.filter(branch_id=user.branch_id)
    else:
        return {"rows": []}
    rows = expiry_alerts(customers)
    return {"rows": rows, "waiting": sum(1 for p in rows if p.follow_up_status != "CONTACTED")}
