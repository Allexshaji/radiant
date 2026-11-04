from django import forms
from accounts.models import Branch,User
from admin_panel.models import LeaveType, ExpenseType


class StaffApprovalForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("branch",)




class BranchForm(forms.ModelForm):

    class Meta:
        model = Branch
        fields = ["name"]

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "w-full p-3 border border-gray-300 rounded-lg",
                    "placeholder": "Enter branch name",
                }
            ),
        }




class LeaveTypeForm(forms.ModelForm):
    class Meta:
        model = LeaveType
        fields = ['name', 'description', 'days_per_year', 'is_active', 'is_paid']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Casual Leave, Sick Leave',
                'required': True
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description of this leave type',
                'required': False
            }),
            'days_per_year': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'required': True
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }


class ExpenseTypeForm(forms.ModelForm):
    class Meta:
        model = ExpenseType
        fields = ['name', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full p-3 border border-gray-300 rounded-lg',
                'placeholder': 'e.g., Electricity, Tea, Milk',
                'required': True
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 rounded border-gray-300 text-emerald-600',
            }),
        }

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        # Staff see this list in a dropdown, so two entries with the same name would confuse them.
        clash = ExpenseType.objects.filter(name__iexact=name)
        if self.instance.pk:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError('An expense with this name already exists.')
        return name