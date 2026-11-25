"""Start the rate list with the four packages from the Package Rate Master sheet.

Rates and validity can be changed later on the Package Rates page.
"""
from decimal import Decimal

from django.db import migrations

STARTING_RATES = [
    # name, massages, rate, validity in months
    ("10 Massage", 10, Decimal("13000"), 6),
    ("15 Massage", 15, Decimal("18000"), 6),
    ("20 Massage", 20, Decimal("22000"), 12),
    ("25 Massage", 25, Decimal("25000"), 12),
]


def add_rates(apps, schema_editor):
    PackageType = apps.get_model("packages", "PackageType")
    for name, massages, rate, months in STARTING_RATES:
        PackageType.objects.get_or_create(
            name=name,
            defaults={"total_massages": massages, "rate": rate, "validity_months": months},
        )


class Migration(migrations.Migration):
    dependencies = [("packages", "0001_initial")]

    operations = [migrations.RunPython(add_rates, migrations.RunPython.noop)]
