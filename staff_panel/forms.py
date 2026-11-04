from django import forms
from django.utils import timezone
from django.forms import inlineformset_factory
from .models import LeaveApplication, LeaveType, Requirement
from admin_panel.models import ExpenseType


from .models import (
    DailyReport,
    WalkInService,
    Revenue,
    PaymentSummary,
    ExpenseItem,
)


class WalkinServicesForm(forms.ModelForm):
    class Meta:
        model = WalkInService

        fields = [
            "total_walkins",
            "treatment_count",
            "package_count",
            "normal_massage_count",
            "consultation_count",
            "sales_count",
        ]

        widgets = {
            "total_walkins": forms.NumberInput(attrs={
                "class": "w-full p-2.5 border border-gray-300 rounded-lg",
            }),

            "treatment_count": forms.NumberInput(attrs={
                "class": "w-full p-2.5 border border-gray-300 rounded-lg",
            }),

            "package_count": forms.NumberInput(attrs={
                "class": "w-full p-2.5 border border-gray-300 rounded-lg",
            }),

            "normal_massage_count": forms.NumberInput(attrs={
                "class": "w-full p-2.5 border border-gray-300 rounded-lg",
            }),

            "consultation_count": forms.NumberInput(attrs={
                "class": "w-full p-2.5 border border-gray-300 rounded-lg",
            }),

            "sales_count": forms.NumberInput(attrs={
                "class": "w-full p-2.5 border border-gray-300 rounded-lg",
            }),
           
        }


class RevenueBreakdownForm(forms.ModelForm):
    class Meta:
        model = Revenue

        fields = [
            "treatment_revenue",
            "massage_revenue",
            "new_package_revenue",
            "consultation_revenue",
            "sales_revenue",
        ]

        widgets = {
            "treatment_revenue": forms.NumberInput(attrs={
                "class": "w-full p-2.5 border border-gray-300 rounded-lg",
                "step": "0.01",
            }),

            "massage_revenue": forms.NumberInput(attrs={
                "class": "w-full p-2.5 border border-gray-300 rounded-lg",
                "step": "0.01",
            }),

            "new_package_revenue": forms.NumberInput(attrs={
                "class": "w-full p-2.5 border border-gray-300 rounded-lg",
                "step": "0.01",
            }),

            "consultation_revenue": forms.NumberInput(attrs={
                "class": "w-full p-2.5 border border-gray-300 rounded-lg",
                "step": "0.01",
            }),

            "sales_revenue": forms.NumberInput(attrs={
                "class": "w-full p-2.5 border border-gray-300 rounded-lg",
                "step": "0.01",
            }),
        }


class PaymentSummaryForm(forms.ModelForm):
    class Meta:
        model = PaymentSummary

        fields = [
            "cash",
            "gpay",
            "card",
        ]

        widgets = {
            "cash": forms.NumberInput(attrs={
                "class": "w-full p-2.5 border border-gray-300 rounded-lg",
                "step": "0.01",
            }),

            "gpay": forms.NumberInput(attrs={
                "class": "w-full p-2.5 border border-gray-300 rounded-lg",
                "step": "0.01",
            }),

            "card": forms.NumberInput(attrs={
                "class": "w-full p-2.5 border border-gray-300 rounded-lg",
                "step": "0.01",
            }),
        }


class ExpenseItemForm(forms.ModelForm):
    # Staff choose the expense from the list the admin has added.
    description = forms.ChoiceField(
        label="Expense",
        choices=[],
        error_messages={"required": "Choose an expense from the list."},
        widget=forms.Select(attrs={
            "class": "w-full p-2.5 border border-gray-300 rounded-lg bg-white",
        }),
    )

    class Meta:
        model = ExpenseItem

        fields = [
            "description",
            "note",
            "amount",
        ]

        widgets = {
            "note": forms.TextInput(attrs={
                "class": "w-full p-2.5 border border-gray-300 rounded-lg",
                "placeholder": "Describe the expense (optional)",
                "maxlength": 255,
            }),

            "amount": forms.NumberInput(attrs={
                "class": "w-full p-2.5 border border-gray-300 rounded-lg",
                "step": "0.01",
                "placeholder": "0.00",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        names = list(
            ExpenseType.objects.filter(is_active=True).values_list("name", flat=True)
        )

        # A row saved before the admin list existed keeps its old name, so it can still be re-saved.
        saved = self.instance.description if self.instance.pk else ""
        if saved and saved not in names:
            names.append(saved)

        placeholder = "Choose expense" if names else "No expenses added yet - ask the admin"

        self.fields["description"].choices = [("", placeholder)] + [(name, name) for name in names]


class RequirementForm(forms.ModelForm):
    """The text box staff use to send a requirement to the admin."""

    class Meta:
        model = Requirement
        fields = ["text"]
        labels = {"text": "Requirement"}
        widgets = {
            "text": forms.Textarea(attrs={
                "rows": 4,
                "class": "w-full p-3 border border-gray-300 rounded-lg",
                "placeholder": "Type the requirement here",
            }),
        }

    def clean_text(self):
        text = (self.cleaned_data.get("text") or "").strip()
        if not text:
            raise forms.ValidationError("Type the requirement before sending.")
        if len(text) > 1000:
            raise forms.ValidationError("Keep the requirement within 1000 characters.")
        return text


ExpenseFormSet = inlineformset_factory(
    DailyReport,
    ExpenseItem,
    form=ExpenseItemForm,
    extra=1,
    can_delete=True,
)



class LeaveApplicationForm(forms.ModelForm):
    """Form for staff to apply for leave"""
    
    class Meta:
        model = LeaveApplication
        fields = ['leave_type', 'start_date', 'end_date', 'reason']
        widgets = {
            'leave_type': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'required': True
            }),
            'end_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'required': True
            }),
            'reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter reason for leave',
                'required': True
            }),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise forms.ValidationError("End date must be after start date")
            if start_date < timezone.now().date():
                raise forms.ValidationError("Cannot apply for past dates")
        
        return cleaned_data

class LeaveApprovalForm(forms.ModelForm):
    """Form for admin to approve/reject leave"""
    
    class Meta:
        model = LeaveApplication
        fields = ['status', 'rejection_reason']
        widgets = {
            'status': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'rejection_reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'If rejecting, provide reason...'
            }),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        reason = cleaned_data.get('rejection_reason')
        
        if status == 'rejected' and not reason:
            raise forms.ValidationError("Rejection reason is required when rejecting a leave")
        
        return cleaned_data