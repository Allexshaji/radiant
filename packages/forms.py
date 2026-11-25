from django import forms
from django.utils import timezone

from accounts.models import Branch

from .models import CustomerPackage, MassageVisit, PackageType


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%d", **kwargs)


class PackageSaleForm(forms.Form):
    """Sell a package. Also used for a renewal, where the customer is already known."""

    branch = forms.ModelChoiceField(queryset=Branch.objects.order_by("name"), required=False)
    customer_name = forms.CharField(max_length=150)
    phone = forms.CharField(max_length=20)
    package_type = forms.ModelChoiceField(queryset=PackageType.objects.filter(is_active=True))
    purchase_date = forms.DateField(widget=DateInput())
    expiry_date = forms.DateField(
        widget=DateInput(), required=False,
        help_text="Leave empty to work it out from the package's validity.",
    )
    rate = forms.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, required=False,
        help_text="Leave empty to use the package's standard rate.",
    )
    amount_paid = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0, initial=0)
    remarks = forms.CharField(max_length=255, required=False)

    def __init__(self, *args, choose_branch=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.choose_branch = choose_branch
        if choose_branch:
            self.fields["branch"].required = True
        else:
            del self.fields["branch"]
        self.fields["package_type"].label_from_instance = (
            lambda t: f"{t.name} - {t.total_massages} massages - Rs. {t.rate:,.0f} - {t.validity_months} months"
        )
        self.fields["purchase_date"].initial = timezone.localdate()

    def clean_phone(self):
        phone = "".join(ch for ch in self.cleaned_data["phone"] if ch.isdigit() or ch == "+")
        if len(phone.lstrip("+")) < 6:
            raise forms.ValidationError("Enter a valid phone number.")
        return phone

    def clean(self):
        data = super().clean()
        bought, ends = data.get("purchase_date"), data.get("expiry_date")
        if bought and bought > timezone.localdate():
            self.add_error("purchase_date", "The purchase date cannot be in the future.")
        if bought and ends and ends < bought:
            self.add_error("expiry_date", "The expiry date cannot be before the purchase date.")
        return data


class PackageEditForm(forms.ModelForm):
    customer_name = forms.CharField(max_length=150)
    phone = forms.CharField(max_length=20)

    class Meta:
        model = CustomerPackage
        fields = ["rate", "amount_paid", "purchase_date", "expiry_date",
                  "follow_up_status", "next_follow_up", "remarks"]
        widgets = {
            "purchase_date": DateInput(),
            "expiry_date": DateInput(),
            "next_follow_up": DateInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer_name"].initial = self.instance.customer.name
        self.fields["phone"].initial = self.instance.customer.phone
        self.order_fields(["customer_name", "phone"])

    def clean_phone(self):
        return PackageSaleForm.clean_phone(self)

    def clean(self):
        data = super().clean()
        bought, ends = data.get("purchase_date"), data.get("expiry_date")
        if bought and ends and ends < bought:
            self.add_error("expiry_date", "The expiry date cannot be before the purchase date.")
        for field in ("rate", "amount_paid"):
            if data.get(field) is not None and data[field] < 0:
                self.add_error(field, "This cannot be negative.")
        return data


class VisitForm(forms.ModelForm):
    class Meta:
        model = MassageVisit
        fields = ["visit_date", "note"]
        widgets = {"visit_date": DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["visit_date"].initial = timezone.localdate()
        self.fields["note"].required = False

    def clean_visit_date(self):
        day = self.cleaned_data["visit_date"]
        if day > timezone.localdate():
            raise forms.ValidationError("A massage cannot be recorded for a future date.")
        return day


class FollowUpForm(forms.ModelForm):
    class Meta:
        model = CustomerPackage
        fields = ["follow_up_status", "next_follow_up", "remarks"]
        widgets = {"next_follow_up": DateInput()}


class PackageTypeForm(forms.ModelForm):
    class Meta:
        model = PackageType
        fields = ["name", "total_massages", "rate", "validity_months", "is_active"]

    def clean(self):
        data = super().clean()
        if data.get("total_massages") is not None and data["total_massages"] < 1:
            self.add_error("total_massages", "A package needs at least one massage.")
        if data.get("validity_months") is not None and data["validity_months"] < 1:
            self.add_error("validity_months", "Validity must be at least one month.")
        return data
