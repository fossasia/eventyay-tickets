from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import Event, Organizer, User
from eventyay.base.models.admin_mail import (
    AdminEmailQueue,
    AdminEmailStatus,
    AdminRecipientGroup,
)
from eventyay.common.forms.mixins import ScheduledAtValidationMixin
from eventyay.common.forms.widgets import EnhancedSelect, EnhancedSelectMultiple
from eventyay.consts import SizeKey
from eventyay.control.forms import CachedFileField, SplitDateTimeField
from eventyay.base.forms.widgets import SplitDateTimePickerWidget


ACCOUNT_STATUS_CHOICES = [
    ('', _('All')),
    ('verified', _('Verified')),
    ('unverified', _('Unverified')),
    ('active', _('Active')),
    ('banned', _('Banned')),
]

USER_ROLE_CHOICES = [
    ('', _('All')),
    ('user', _('User')),
    ('organiser', _('Organiser')),
    ('staff', _('Staff')),
    ('admin', _('Platform admin')),
]

EVENT_STATUS_CHOICES = [
    ('', _('All')),
    ('live', _('Live')),
    ('draft', _('Draft')),
    ('past', _('Past')),
]


class AdminComposeForm(ScheduledAtValidationMixin, forms.Form):
    recipient_group = forms.ChoiceField(
        label=_('Recipient group'),
        choices=AdminRecipientGroup.choices,
        initial=AdminRecipientGroup.ALL_ORGANISERS,
        widget=EnhancedSelect(attrs={
            'title': _('Recipient group'),
            'placeholder': _('Select recipient group'),
        }),
    )

    account_status = forms.ChoiceField(
        label=_('Account status'),
        choices=ACCOUNT_STATUS_CHOICES,
        required=False,
        widget=EnhancedSelect(attrs={
            'title': _('Account status'),
            'placeholder': _('All'),
        }),
    )

    user_role = forms.ChoiceField(
        label=_('User role'),
        choices=USER_ROLE_CHOICES,
        required=False,
        widget=EnhancedSelect(attrs={
            'title': _('User role'),
            'placeholder': _('All'),
        }),
    )

    language = forms.ChoiceField(
        label=_('Language / locale'),
        required=False,
        choices=[],
        widget=EnhancedSelect(attrs={
            'title': _('Language / locale'),
            'placeholder': _('All'),
        }),
    )

    selected_organisers = forms.ModelMultipleChoiceField(
        queryset=Organizer.objects.none(),
        label=_('Selected organisers'),
        required=False,
        widget=EnhancedSelectMultiple(attrs={
            'title': _('Select organisers'),
            'placeholder': _('Select organisers'),
        }),
    )

    selected_events = forms.ModelMultipleChoiceField(
        queryset=Event.objects.none(),
        label=_('Selected events'),
        required=False,
        widget=EnhancedSelectMultiple(attrs={
            'title': _('Select events'),
            'placeholder': _('Select events'),
        }),
    )

    selected_users = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        label=_('Selected users'),
        required=False,
        widget=EnhancedSelectMultiple(attrs={
            'title': _('Select users'),
            'placeholder': _('Select users'),
        }),
    )

    event_status = forms.ChoiceField(
        label=_('Event status'),
        choices=EVENT_STATUS_CHOICES,
        required=False,
        widget=EnhancedSelect(attrs={
            'title': _('Event status'),
            'placeholder': _('All'),
        }),
    )

    created_after = forms.DateTimeField(
        label=_('Created after'),
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'placeholder': _('mm/dd/yyyy')}),
    )

    created_before = forms.DateTimeField(
        label=_('Created before'),
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'placeholder': _('mm/dd/yyyy')}),
    )

    exclude_admins = forms.BooleanField(
        label=_('Exclude platform admins'),
        required=False,
    )

    exclude_inactive = forms.BooleanField(
        label=_('Exclude inactive users'),
        required=False,
    )

    exclude_unconfirmed_email = forms.BooleanField(
        label=_('Exclude users without confirmed email'),
        required=False,
    )

    reply_to = forms.EmailField(
        label=_('Reply-To'),
        required=False,
        help_text=_('Change the Reply-To address if you do not want to use the default platform sender address.'),
        widget=forms.EmailInput(attrs={'placeholder': 'name@yourdomain.com'}),
    )

    bcc = forms.CharField(
        label=_('BCC'),
        required=False,
        help_text=_('Enter comma-separated BCC addresses. Recipients will not see each other.'),
        widget=forms.TextInput(attrs={'placeholder': 'bcc1@domain.com, bcc2@domain.com'}),
    )

    subject = forms.CharField(
        label=_('Subject'),
        max_length=500,
        widget=forms.TextInput(attrs={'placeholder': _('Email subject')}),
    )

    message = forms.CharField(
        label=_('Message'),
        widget=forms.Textarea(attrs={
            'rows': 12,
            'class': 'rich-editor-content',
        }),
    )

    attachment = CachedFileField(
        label=_('Attachment'),
        required=False,
        ext_whitelist=(
            '.png', '.jpg', '.gif', '.jpeg', '.pdf', '.txt', '.docx',
            '.gif', '.svg', '.pptx', '.ppt', '.doc', '.xlsx', '.xls',
            '.jfif', '.heic', '.heif', '.pages', '.bmp', '.tif', '.tiff',
        ),
        help_text=_(
            'Support for up to 10.0MB. Recommended: PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX, PNG, JPG, JPEG.'
        ),
        max_size=settings.MAX_SIZE_CONFIG.get(SizeKey.UPLOAD_SIZE_OTHER, 10 * 1024 * 1024),
    )

    test_email = forms.EmailField(
        label=_('Test email address'),
        required=False,
        widget=forms.EmailInput(attrs={'placeholder': 'name@domain.com'}),
    )

    scheduled_at = SplitDateTimeField(
        widget=SplitDateTimePickerWidget(),
        label=_('Schedule for later'),
        required=False,
        help_text=_('Leave empty to add to outbox. If set, the email will be sent at this time.'),
    )

    send_immediately = forms.BooleanField(
        label=_('Send immediately'),
        required=False,
        help_text=_('If checked, the email will be sent immediately instead of being added to the outbox.'),
    )

    def __init__(self, *args, draft_save: bool = False, **kwargs):
        self.draft_save = draft_save
        super().__init__(*args, **kwargs)

        lang_choices = [('', _('All'))]
        lang_choices.extend(settings.LANGUAGES)
        self.fields['language'].choices = lang_choices

        self.fields['selected_organisers'].queryset = Organizer.objects.all().order_by('name')
        self.fields['selected_events'].queryset = Event.objects.all().order_by('name')
        self.fields['selected_users'].queryset = (
            User.objects.filter(is_active=True)
            .exclude(email__isnull=True)
            .exclude(email='')
            .order_by('email')
        )

        if draft_save:
            self.fields['subject'].required = False
            self.fields['message'].required = False

    def clean(self):
        cleaned = super().clean()
        if cleaned is None:
            return cleaned

        send_immediately = cleaned.get('send_immediately', False)
        scheduled_at = cleaned.get('scheduled_at')
        if send_immediately and scheduled_at:
            raise forms.ValidationError(
                _('You cannot select "Send immediately" and also specify a scheduled time.')
            )

        return cleaned

    def clean_bcc(self):
        bcc = self.cleaned_data.get('bcc', '')
        if bcc:
            from django.core.validators import validate_email

            for addr in bcc.split(','):
                addr = addr.strip()
                if addr:
                    try:
                        validate_email(addr)
                    except forms.ValidationError:
                        raise forms.ValidationError(
                            _('Invalid email address in BCC: %(addr)s'),
                            params={'addr': addr},
                        )
        return bcc


class AdminComposeRecipientsForm(forms.Form):
    """
    Lightweight form for the AJAX recipient count / preview endpoint.
    Contains only the filter fields from AdminComposeForm.
    """

    recipient_group = forms.ChoiceField(
        choices=AdminRecipientGroup.choices,
        required=True,
    )
    account_status = forms.ChoiceField(choices=ACCOUNT_STATUS_CHOICES, required=False)
    user_role = forms.ChoiceField(choices=USER_ROLE_CHOICES, required=False)
    language = forms.ChoiceField(choices=[], required=False)
    event_status = forms.ChoiceField(choices=EVENT_STATUS_CHOICES, required=False)
    created_after = forms.DateTimeField(required=False)
    created_before = forms.DateTimeField(required=False)
    selected_organisers = forms.CharField(required=False)
    selected_events = forms.CharField(required=False)
    selected_users = forms.CharField(required=False)
    exclude_admins = forms.BooleanField(required=False)
    exclude_inactive = forms.BooleanField(required=False)
    exclude_unconfirmed_email = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang_choices = [('', _('All'))]
        lang_choices.extend(settings.LANGUAGES)
        self.fields['language'].choices = lang_choices
