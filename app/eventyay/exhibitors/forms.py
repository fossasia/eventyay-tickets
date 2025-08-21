from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from .models import ExhibitorInfo, ContactRequest, ExhibitorStaff, ExhibitorLink


class ExhibitorForm(forms.ModelForm):
    """Form for creating and editing exhibitors"""
    
    class Meta:
        model = ExhibitorInfo
        fields = [
            'event', 'name', 'tagline', 'description', 'url', 'email',
            'logo', 'banner', 'booth_name', 'highlighted_room_id',
            'contact_enabled', 'lead_scanning_enabled', 'allow_voucher_access',
            'allow_lead_access', 'lead_scanning_scope_by_device',
            'is_active', 'featured', 'sort_order'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter exhibitor name')
            }),
            'tagline': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter tagline')
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': _('Enter description')
            }),
            'url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': _('https://example.com')
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': _('contact@example.com')
            }),
            'booth_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter booth name')
            }),
            'highlighted_room_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Video room ID')
            }),
            'sort_order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0
            }),
            'logo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'banner': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*,video/*'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Limit event choices based on user permissions
        if user and not user.is_staff:
            # Non-staff users can only create exhibitors for events they have access to
            from eventyay.base.models import Event
            accessible_events = Event.objects.filter(
                # Add your event access logic here
                # For now, allow all events
            )
            self.fields['event'].queryset = accessible_events
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name or len(name.strip()) < 2:
            raise ValidationError(_('Exhibitor name must be at least 2 characters long.'))
        return name.strip()
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and '@' not in email:
            raise ValidationError(_('Please enter a valid email address.'))
        return email
    
    def clean_logo(self):
        logo = self.cleaned_data.get('logo')
        if logo:
            # Check file size (max 5MB)
            if logo.size > 5 * 1024 * 1024:
                raise ValidationError(_('Logo file size must be less than 5MB.'))
            
            # Check file type
            allowed_types = ['image/jpeg', 'image/png', 'image/webp']
            if hasattr(logo, 'content_type') and logo.content_type not in allowed_types:
                raise ValidationError(_('Logo must be a JPEG, PNG, or WebP image.'))
        
        return logo
    
    def clean_banner(self):
        banner = self.cleaned_data.get('banner')
        if banner:
            # Check file size (max 50MB for videos, 10MB for images)
            max_size = 50 * 1024 * 1024 if banner.content_type.startswith('video/') else 10 * 1024 * 1024
            if banner.size > max_size:
                size_limit = '50MB' if banner.content_type.startswith('video/') else '10MB'
                raise ValidationError(_(f'Banner file size must be less than {size_limit}.'))
            
            # Check file type
            allowed_types = [
                'image/jpeg', 'image/png', 'image/webp',
                'video/mp4', 'video/webm'
            ]
            if hasattr(banner, 'content_type') and banner.content_type not in allowed_types:
                raise ValidationError(_('Banner must be an image (JPEG, PNG, WebP) or video (MP4, WebM).'))
        
        return banner


class ContactForm(forms.ModelForm):
    """Form for attendees to contact exhibitors"""
    
    class Meta:
        model = ContactRequest
        fields = ['attendee_name', 'attendee_email', 'subject', 'message']
        widgets = {
            'attendee_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Your name'),
                'required': True
            }),
            'attendee_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': _('your.email@example.com'),
                'required': True
            }),
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Subject'),
                'required': True
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('Your message'),
                'required': True
            }),
        }
    
    def clean_attendee_name(self):
        name = self.cleaned_data.get('attendee_name')
        if not name or len(name.strip()) < 2:
            raise ValidationError(_('Please enter your full name.'))
        return name.strip()
    
    def clean_attendee_email(self):
        email = self.cleaned_data.get('attendee_email')
        if not email or '@' not in email:
            raise ValidationError(_('Please enter a valid email address.'))
        return email.lower().strip()
    
    def clean_subject(self):
        subject = self.cleaned_data.get('subject')
        if not subject or len(subject.strip()) < 3:
            raise ValidationError(_('Subject must be at least 3 characters long.'))
        return subject.strip()
    
    def clean_message(self):
        message = self.cleaned_data.get('message')
        if not message or len(message.strip()) < 10:
            raise ValidationError(_('Message must be at least 10 characters long.'))
        return message.strip()


class ExhibitorStaffForm(forms.ModelForm):
    """Form for managing exhibitor staff"""
    
    class Meta:
        model = ExhibitorStaff
        fields = ['user', 'role', 'can_manage_leads', 'can_edit_info']
        widgets = {
            'user': forms.Select(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
            'can_manage_leads': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_edit_info': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        exhibitor = kwargs.pop('exhibitor', None)
        super().__init__(*args, **kwargs)
        
        if exhibitor:
            # Exclude users already assigned to this exhibitor
            from django.contrib.auth import get_user_model
            User = get_user_model()
            existing_staff_users = exhibitor.staff.values_list('user_id', flat=True)
            self.fields['user'].queryset = User.objects.exclude(
                id__in=existing_staff_users
            ).filter(is_active=True)


class ExhibitorLinkForm(forms.ModelForm):
    """Form for managing exhibitor links"""
    
    class Meta:
        model = ExhibitorLink
        fields = ['url', 'display_text', 'category', 'sorting_priority', 'is_active']
        widgets = {
            'url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': _('https://example.com')
            }),
            'display_text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Link text')
            }),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'sorting_priority': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean_url(self):
        url = self.cleaned_data.get('url')
        if not url or not (url.startswith('http://') or url.startswith('https://')):
            raise ValidationError(_('Please enter a valid URL starting with http:// or https://'))
        return url
    
    def clean_display_text(self):
        text = self.cleaned_data.get('display_text')
        if not text or len(text.strip()) < 2:
            raise ValidationError(_('Display text must be at least 2 characters long.'))
        return text.strip()


class ExhibitorSearchForm(forms.Form):
    """Form for searching exhibitors"""
    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Search exhibitors...'),
            'autocomplete': 'off'
        })
    )
    featured = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    order_by = forms.ChoiceField(
        choices=[
            ('sort_order', _('Default Order')),
            ('name', _('Name')),
            ('created_at', _('Newest First')),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class BulkExhibitorActionForm(forms.Form):
    """Form for bulk actions on exhibitors"""
    ACTION_CHOICES = [
        ('activate', _('Activate')),
        ('deactivate', _('Deactivate')),
        ('feature', _('Mark as Featured')),
        ('unfeature', _('Remove Featured')),
        ('delete', _('Delete')),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    exhibitor_ids = forms.CharField(
        widget=forms.HiddenInput()
    )
    
    def clean_exhibitor_ids(self):
        ids_str = self.cleaned_data.get('exhibitor_ids', '')
        try:
            ids = [int(id_str.strip()) for id_str in ids_str.split(',') if id_str.strip()]
            if not ids:
                raise ValidationError(_('Please select at least one exhibitor.'))
            return ids
        except ValueError:
            raise ValidationError(_('Invalid exhibitor selection.'))