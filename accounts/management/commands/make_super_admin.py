from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from accounts.models import User


class Command(BaseCommand):
    help = (
        "Turn an existing account into a Super Admin. "
        "Give the username or the email address of the account."
    )

    def add_arguments(self, parser):
        parser.add_argument("login", help="Username or email of the account to promote")

    def handle(self, *args, **options):
        login = options["login"].strip()
        account = User.objects.filter(Q(username=login) | Q(email__iexact=login)).first()
        if account is None:
            raise CommandError(f"No account found for '{login}'.")

        account.role = User.SUPER_ADMIN
        account.is_active = True
        account.is_approved = True
        account.blocked_sections = []
        account.save(update_fields=["role", "is_active", "is_approved", "blocked_sections"])
        self.stdout.write(self.style.SUCCESS(f"'{account.username}' is now a Super Admin."))
