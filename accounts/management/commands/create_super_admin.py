from getpass import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.core.validators import validate_email

from accounts.models import User


class Command(BaseCommand):
    help = "Create a new Super Admin account. Asks for the username, email and password in the Terminal."

    def handle(self, *args, **options):
        self.stdout.write("Create a new Super Admin account. Press Ctrl + C to cancel.")

        username = self.ask_username()
        email = self.ask_email()
        full_name = input("Full name (optional, press Enter to skip): ").strip()[:150]
        password = self.ask_password(username, email)

        User.objects.create_user(
            username=username,
            email=email,
            password=password,
            full_name=full_name,
            role=User.SUPER_ADMIN,
            is_active=True,
            is_approved=True,
        )
        self.stdout.write(self.style.SUCCESS(
            f"Super Admin '{username}' was created. Log in at http://127.0.0.1:8000/ "
            "and you will land on the Super Admin Dashboard."
        ))

    def ask_username(self):
        while True:
            username = input("Username: ").strip()
            if not username:
                self.stderr.write("The username cannot be empty.")
            elif len(username) > 150:
                self.stderr.write("The username must be 150 characters or fewer.")
            elif User.objects.filter(username=username).exists():
                self.stderr.write("That username is already taken. Choose another.")
            else:
                return username

    def ask_email(self):
        while True:
            email = input("Email: ").strip()
            try:
                validate_email(email)
            except ValidationError:
                self.stderr.write("Enter a valid email address.")
                continue
            if User.objects.filter(email__iexact=email).exists():
                self.stderr.write("That email is already used by another account. Choose another.")
                continue
            return email

    def ask_password(self, username, email):
        while True:
            password = getpass("Password (typing is hidden): ")
            confirm = getpass("Type the password again: ")
            if password != confirm:
                self.stderr.write("The two passwords do not match. Try again.")
                continue
            try:
                validate_password(password, user=User(username=username, email=email))
            except ValidationError as error:
                for message in error.messages:
                    self.stderr.write(message)
                continue
            return password
