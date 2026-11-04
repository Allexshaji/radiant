from django.contrib.auth.forms import UserCreationForm
from .models import User
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError


class ApprovedAuthenticationForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)

        if user.role == User.STAFF and not user.is_approved:
            raise ValidationError(
                "Your account is waiting for administrator approval."
            )

class FirstAdminForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "email")

class StaffRegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("full_name", "email", "branch")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        user.role = User.STAFF
        user.is_approved = False

        if commit:
            user.save()

        return user