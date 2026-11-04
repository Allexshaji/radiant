from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from accounts.access import ADMIN_SECTIONS
from accounts.models import User

INPUT_CLASS = (
    "w-full px-3.5 py-2.5 border border-gray-300 rounded-lg text-sm text-gray-900 bg-white "
    "focus:outline-none focus:ring-2 focus:ring-[#273B30]/20 focus:border-[#273B30]"
)


class AdminAccountForm(forms.ModelForm):
    """Create or edit an Admin or Super Admin account. The admin areas are read from the request by the view."""

    password = forms.CharField(
        label="Password",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    confirm_password = forms.CharField(
        label="Confirm password",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = ["full_name", "username", "email", "role", "branch"]
        labels = {"full_name": "Full name", "role": "Account type", "branch": "Branch"}
        help_texts = {
            "branch": "Required for an Admin. An Admin sees only the staff of this branch. A Super Admin sees every branch.",
        }

    def __init__(self, *args, editing=False, is_self=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.editing = editing

        # The widget must be set before the choices, so the radio buttons receive the choices.
        self.fields["role"].widget = forms.RadioSelect()
        self.fields["role"].choices = [(User.SUPER_ADMIN, "Super Admin"), (User.ADMIN, "Admin")]
        if not self.instance.pk:
            self.fields["role"].initial = User.ADMIN  # new accounts start as Admin
        self.fields["email"].required = True
        self.fields["branch"].required = False
        self.fields["branch"].empty_label = "Choose a branch"
        self.fields["password"].required = not editing
        self.fields["confirm_password"].required = not editing
        if editing:
            self.fields["password"].help_text = "Leave empty to keep the current password."
        if is_self:
            # A Super Admin cannot change their own account type.
            self.fields["role"].disabled = True

        for name, field in self.fields.items():
            if name != "role":  # radio buttons are styled in the template
                field.widget.attrs.setdefault("class", INPUT_CLASS)

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        confirm = cleaned.get("confirm_password")

        if cleaned.get("role") == User.ADMIN and not cleaned.get("branch"):
            self.add_error("branch", "Choose the branch this admin works in.")

        if password or confirm:
            if password != confirm:
                self.add_error("confirm_password", "The two passwords do not match.")
            else:
                try:
                    validate_password(password, user=self.instance)
                except ValidationError as error:
                    self.add_error("password", error)
        return cleaned

    def save(self, commit=True, selected_sections=()):
        account = super().save(commit=False)

        # Admin areas that are NOT ticked are stored as blocked. Super Admins have no blocked areas.
        selected = set(selected_sections)
        if account.role == User.ADMIN:
            account.blocked_sections = [key for key, _label, _text in ADMIN_SECTIONS if key not in selected]
        else:
            # A Super Admin is not tied to a branch and has no closed areas.
            account.blocked_sections = []
            account.branch = None
        account.is_approved = True

        password = self.cleaned_data.get("password")
        if password:
            account.set_password(password)

        if commit:
            account.save()
        return account
