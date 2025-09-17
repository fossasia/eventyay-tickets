from django import forms
from django.utils.translation import gettext_lazy as _
from i18nfield.forms import I18nFormField, I18nTextarea, I18nTextInput

from .models import ExhibitorInfo, ExhibitorSettings


class ExhibitorInfoForm(forms.ModelForm):
    """Form for creating and editing exhibitor information."""
    
    class Meta:
        model = ExhibitorInfo
        fields = [
            'name', 'description', 'url', 'email', 'logo',
            'booth_id', 'booth_name', 'lead_scanning_enabled',
            'allow_voucher_access', 'allow_lead_access',
            'lead_scanning_scope_by_device'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter exhibitor name')
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('Enter exhibitor description')
            }),
            'url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': _('https://example.com')
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': _('contact@example.com')
            }),
            'logo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'booth_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Leave empty to auto-generate')
            }),
            'booth_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g., Booth A1')
            }),
            'lead_scanning_enabled': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'allow_voucher_access': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'allow_lead_access': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'lead_scanning_scope_by_device': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def clean_name(self):
        """Validate exhibitor name."""
        name = self.cleaned_data.get('name')
        if name and len(name.strip()) < 2:
            raise forms.ValidationError(
                _('Exhibitor name must be at least 2 characters long.')
            )
        return name.strip() if name else name
    
    def clean_booth_id(self):
        """Validate booth ID uniqueness."""
        booth_id = self.cleaned_data.get('booth_id')
        if booth_id:
            # Check for uniqueness, excluding current instance
            queryset = ExhibitorInfo.objects.filter(booth_id=booth_id)
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            
            if queryset.exists():
                raise forms.ValidationError(
                    _('This booth ID is already in use.')
                )
        
        return booth_id
    
    def clean_logo(self):
        """Validate logo file."""
        logo = self.cleaned_data.get('logo')
        if logo:
            # Check file size (max 5MB)
            if logo.size > 5 * 1024 * 1024:
                raise forms.ValidationError(
                    _('Logo file size must be less than 5MB.')
                )
            
            # Check file type
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            if logo.content_type not in allowed_types:
                raise forms.ValidationError(
                    _('Logo must be a JPEG, PNG, GIF, or WebP image.')
                )
        
        return logo


class ExhibitorSettingsForm(forms.ModelForm):
    """Form for exhibitor plugin settings."""
    
    FIELD_CHOICES = [
        ('attendee_city', _('City')),
        ('attendee_country', _('Country')),
        ('attendee_company', _('Company')),
        ('attendee_phone', _('Phone')),
        ('attendee_job_title', _('Job Title')),
    ]
    
    allowed_fields = forms.MultipleChoiceField(
        choices=FIELD_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        }),
        required=False,
        label=_('Additional fields to include in lead data'),
        help_text=_('Select which additional attendee fields exhibitors can access.')
    )
    
    class Meta:
        model = ExhibitorSettings
        fields = [
            'exhibitors_access_mail_subject',
            'exhibitors_access_mail_body',
            'allowed_fields',
            'enable_public_directory',
            'enable_lead_export',
            'lead_retention_days'
        ]
        widgets = {
            'exhibitors_access_mail_subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Subject for exhibitor access emails')
            }),
            'exhibitors_access_mail_body': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': _('Email body template for exhibitor access')
            }),
            'enable_public_directory': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'enable_lead_export': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'lead_retention_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 3650
            }),
        }
    
    def clean_lead_retention_days(self):
        """Validate lead retention period."""
        days = self.cleaned_data.get('lead_retention_days')
        if days and (days < 1 or days > 3650):
            raise forms.ValidationError(
                _('Lead retention period must be between 1 and 3650 days.')
            )
        return days


class LeadSearchForm(forms.Form):
    """Form for searching and filtering leads."""
    
    FOLLOW_UP_CHOICES = [
        ('', _('All statuses')),
        ('pending', _('Pending')),
        ('contacted', _('Contacted')),
        ('qualified', _('Qualified')),
        ('converted', _('Converted')),
    ]
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Search by attendee name or email')
        }),
        label=_('Search')
    )
    
    follow_up_status = forms.ChoiceField(
        choices=FOLLOW_UP_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        label=_('Follow-up Status')
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label=_('Scanned From')
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label=_('Scanned To')
    )


class BulkExhibitorActionForm(forms.Form):
    """Form for bulk actions on exhibitors."""
    
    ACTION_CHOICES = [
        ('', _('Select action')),
        ('enable_lead_scanning', _('Enable lead scanning')),
        ('disable_lead_scanning', _('Disable lead scanning')),
        ('regenerate_keys', _('Regenerate access keys')),
        ('export_data', _('Export exhibitor data')),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        label=_('Action')
    )
    
    exhibitors = forms.ModelMultipleChoiceField(
        queryset=ExhibitorInfo.objects.none(),
        widget=forms.CheckboxSelectMultiple(),
        required=True,
        label=_('Select Exhibitors')
    )
    
    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        if event:
            self.fields['exhibitors'].queryset = ExhibitorInfo.objects.filter(
                event=event,
                is_active=True
            ).order_by('name')