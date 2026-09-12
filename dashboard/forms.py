from django import forms
from .models import DatabaseResource, DatabaseTransaction, Information, RESOURCE_TIERS, SIZE_TIER_CHOICES

class DatabaseResourceForm(forms.ModelForm):
    class Meta:
        model = DatabaseResource
        fields = ['name','description','category','capacity_units']

class TransactionSessionForm(forms.ModelForm):
    """Requests a preset size tier (Small/Medium/Large/X-Large) resolved
    per-category via RESOURCE_TIERS, instead of an arbitrary unit count —
    'Custom' falls back to an exact number for cases the presets don't fit."""

    size = forms.ChoiceField(choices=SIZE_TIER_CHOICES, initial='Small', label='Size')
    custom_units = forms.IntegerField(
        required=False, min_value=1, label='Custom units',
        help_text='Only used when Size is set to Custom.',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['resource'].queryset = DatabaseResource.objects.filter(is_active=True)
        self.fields['requested_units'].required = False
        self.fields['requested_units'].widget = forms.HiddenInput()

    class Meta:
        model = DatabaseTransaction
        fields = ['resource', 'requested_units']

    def clean(self):
        cleaned = super().clean()
        resource = cleaned.get('resource')
        size = cleaned.get('size')

        if size == 'Custom':
            units = cleaned.get('custom_units')
            if resource and not units:
                self.add_error('custom_units', 'Enter a unit count for a custom-sized request.')
        elif resource and size:
            tiers = RESOURCE_TIERS.get(resource.category, RESOURCE_TIERS['Other'])
            units = tiers.get(size)
        else:
            units = None

        cleaned['requested_units'] = units
        return cleaned



class InformationForm(forms.ModelForm):
    class Meta:
        model = Information
        fields = ['content']

class TransactionStateForm(forms.Form):
    """Captures the operator's requested next lifecycle state; the actual
    transition is validated and applied by TransactionService, not this form."""
    status = forms.ChoiceField(choices=DatabaseTransaction.TRANSACTION_STATE_CHOICES, label='Transaction State')

class DatabaseResourceCapacityForm(forms.ModelForm):
    class Meta:
        model = DatabaseResource
        fields = ['capacity_units']
