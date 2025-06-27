from django import forms
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy
from django_scopes.forms import SafeModelMultipleChoiceField
from i18nfield.forms import I18nFormField, I18nTextarea, I18nTextInput

from pretix.base.channels import get_all_sales_channels
from pretix.base.email import get_available_placeholders
from pretix.base.forms import PlaceholderValidator, SettingsForm
from pretix.base.forms.widgets import SplitDateTimePickerWidget
from pretix.base.models import CachedFile, CheckinList, Item, Order, SubEvent
from pretix.control.forms import CachedFileField
from pretix.control.forms.widgets import Select2, Select2Multiple
from .models import QueuedMail

MAIL_SEND_ORDER_PLACED_ATTENDEE_HELP = _( 'If the order contains attendees with email addresses different from the person who orders the ' 'tickets, the following email will be sent out to the attendees.' )

def contains_web_channel_validate(value):
    if 'web' not in value:
        raise ValidationError(_("The 'web' sales channel must be selected."))

class MailForm(forms.Form):
    recipients = forms.ChoiceField(label=_('Send email to'), widget=forms.RadioSelect, initial='orders', choices=[])
    sendto = forms.MultipleChoiceField()  # overridden later
    subject = forms.CharField(label=_('Subject'))
    message = forms.CharField(label=_('Message'))
    attachment = CachedFileField(
        label=_('Attachment'),
        required=False,
        ext_whitelist=(
            '.png',
            '.jpg',
            '.gif',
            '.jpeg',
            '.pdf',
            '.txt',
            '.docx',
            '.gif',
            '.svg',
            '.pptx',
            '.ppt',
            '.doc',
            '.xlsx',
            '.xls',
            '.jfif',
            '.heic',
            '.heif',
            '.pages',
            '.bmp',
            '.tif',
            '.tiff',
        ),
        help_text=_(
            'Sending an attachment increases the chance of your email not arriving or being sorted into spam folders. We recommend only using PDFs '
            'of no more than 2 MB in size.'
        ),
        max_size=10 * 1024 * 1024,
    )  # TODO i18n
    items = forms.ModelMultipleChoiceField(
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'scrolling-multiple-choice'}),
        label=_('Only send to people who bought'),
        required=True,
        queryset=Item.objects.none(),
    )
    filter_checkins = forms.BooleanField(label=_('Filter check-in status'), required=False)
    checkin_lists = SafeModelMultipleChoiceField(
        queryset=CheckinList.objects.none(), required=False
    )  # overridden later
    not_checked_in = forms.BooleanField(label=_('Send to customers not checked in'), required=False)
    subevent = forms.ModelChoiceField(
        SubEvent.objects.none(),
        label=_('Only send to customers of'),
        required=False,
        empty_label=pgettext_lazy('subevent', 'All dates'),
    )
    subevents_from = forms.SplitDateTimeField(
        widget=SplitDateTimePickerWidget(),
        label=pgettext_lazy('subevent', 'Only send to customers of dates starting at or after'),
        required=False,
    )
    subevents_to = forms.SplitDateTimeField(
        widget=SplitDateTimePickerWidget(),
        label=pgettext_lazy('subevent', 'Only send to customers of dates starting before'),
        required=False,
    )
    created_from = forms.SplitDateTimeField(
        widget=SplitDateTimePickerWidget(),
        label=pgettext_lazy('subevent', 'Only send to customers with orders created after'),
        required=False,
    )
    created_to = forms.SplitDateTimeField(
        widget=SplitDateTimePickerWidget(),
        label=pgettext_lazy('subevent', 'Only send to customers with orders created before'),
        required=False,
    )

    def clean(self):
        d = super().clean()
        if d.get('subevent') and (d.get('subevents_from') or d.get('subevents_to')):
            raise ValidationError(
                pgettext_lazy(
                    'subevent',
                    'Please either select a specific date or a date range, not both.',
                )
            )
        if bool(d.get('subevents_from')) != bool(d.get('subevents_to')):
            raise ValidationError(
                pgettext_lazy(
                    'subevent',
                    'If you set a date range, please set both a start and an end.',
                )
            )
        return d

    def _set_field_placeholders(self, fn, base_parameters):
        phs = ['{%s}' % p for p in sorted(get_available_placeholders(self.event, base_parameters).keys())]
        ht = _('Available placeholders: {list}').format(list=', '.join(phs))
        if self.fields[fn].help_text:
            self.fields[fn].help_text += ' ' + str(ht)
        else:
            self.fields[fn].help_text = ht
        self.fields[fn].validators.append(PlaceholderValidator(phs))

    def __init__(self, *args, **kwargs):
        event = self.event = kwargs.pop('event')
        super().__init__(*args, **kwargs)

        recp_choices = [('orders', _('Everyone who created a ticket order'))]
        if event.settings.attendee_emails_asked:
            recp_choices += [
                (
                    'attendees',
                    _('Every attendee (falling back to the order contact when no attendee email address is given)'),
                ),
                (
                    'both',
                    _('Both (all order contact addresses and all attendee email addresses)'),
                ),
            ]
        self.fields['recipients'].choices = recp_choices

        self.fields['subject'] = I18nFormField(
            label=_('Subject'),
            widget=I18nTextInput,
            required=True,
            locales=event.settings.get('locales'),
        )
        self.fields['message'] = I18nFormField(
            label=_('Message'),
            widget=I18nTextarea,
            required=True,
            locales=event.settings.get('locales'),
        )
        self._set_field_placeholders('subject', ['event', 'order', 'position_or_address'])
        self._set_field_placeholders('message', ['event', 'order', 'position_or_address'])
        choices = [(e, l) for e, l in Order.STATUS_CHOICE if e != 'n']
        choices.insert(0, ('na', _('payment pending (except unapproved)')))
        choices.insert(0, ('pa', _('approval pending')))
        if not event.settings.get('payment_term_expire_automatically', as_type=bool):
            choices.append(('overdue', _('pending with payment overdue')))
        self.fields['sendto'] = forms.MultipleChoiceField(
            label=_('Send to customers with order status'),
            widget=forms.CheckboxSelectMultiple(attrs={'class': 'scrolling-multiple-choice'}),
            choices=choices,
        )
        if not self.initial.get('sendto'):
            self.initial['sendto'] = ['p', 'na']
        elif 'n' in self.initial['sendto']:
            self.initial['sendto'].append('pa')
            self.initial['sendto'].append('na')

        self.fields['items'].queryset = event.items.all()
        if not self.initial.get('items'):
            self.initial['items'] = event.items.all()

        self.fields['checkin_lists'].queryset = event.checkin_lists.all()
        self.fields['checkin_lists'].widget = Select2Multiple(
            attrs={
                'data-model-select2': 'generic',
                'data-select2-url': reverse(
                    'control:event.orders.checkinlists.select2',
                    kwargs={
                        'event': event.slug,
                        'organizer': event.organizer.slug,
                    },
                ),
                'data-placeholder': _('Send to customers checked in on list'),
            }
        )
        self.fields['checkin_lists'].widget.choices = self.fields['checkin_lists'].choices
        self.fields['checkin_lists'].label = _('Send to customers checked in on list')

        if event.has_subevents:
            self.fields['subevent'].queryset = event.subevents.all()
            self.fields['subevent'].widget = Select2(
                attrs={
                    'data-model-select2': 'event',
                    'data-select2-url': reverse(
                        'control:event.subevents.select2',
                        kwargs={
                            'event': event.slug,
                            'organizer': event.organizer.slug,
                        },
                    ),
                    'data-placeholder': pgettext_lazy('subevent', 'Date'),
                }
            )
            self.fields['subevent'].widget.choices = self.fields['subevent'].choices
        else:
            del self.fields['subevent']
            del self.fields['subevents_from']
            del self.fields['subevents_to']

class MailContentSettingsForm(SettingsForm):
    mail_text_order_placed = I18nFormField(
        label=_('Text sent to order contact address'),
        required=False,
        widget=I18nTextarea,
    )
    mail_send_order_placed_attendee = forms.BooleanField(
        label=_('Send an email to attendees'),
        help_text= MAIL_SEND_ORDER_PLACED_ATTENDEE_HELP,
        required=False,
    )
    mail_text_order_placed_attendee = I18nFormField(
        label=_('Text sent to attendees'),
        required=False,
        widget=I18nTextarea,
    )

    mail_text_order_paid = I18nFormField(
        label=_('Text sent to order contact address'),
        required=False,
        widget=I18nTextarea,
    )
    mail_send_order_paid_attendee = forms.BooleanField(
        label=_('Send an email to attendees'),
        help_text= MAIL_SEND_ORDER_PLACED_ATTENDEE_HELP,
        required=False,
    )
    mail_text_order_paid_attendee = I18nFormField(
        label=_('Text sent to attendees'),
        required=False,
        widget=I18nTextarea,
    )

    mail_text_order_free = I18nFormField(
        label=_('Text sent to order contact address'),
        required=False,
        widget=I18nTextarea,
    )
    mail_send_order_free_attendee = forms.BooleanField(
        label=_('Send an email to attendees'),
        help_text= MAIL_SEND_ORDER_PLACED_ATTENDEE_HELP,
        required=False,
    )
    mail_text_order_free_attendee = I18nFormField(
        label=_('Text sent to attendees'),
        required=False,
        widget=I18nTextarea,
    )

    mail_text_resend_link = I18nFormField(
        label=_('Text (sent by admin)'),
        required=False,
        widget=I18nTextarea,
    )
    mail_text_resend_all_links = I18nFormField(
        label=_('Text (requested by user)'),
        required=False,
        widget=I18nTextarea,
    )

    mail_text_order_changed = I18nFormField(
        label=_('Text'),
        required=False,
        widget=I18nTextarea,
    )

    mail_days_order_expire_warning = forms.IntegerField(
        label=_('Number of days'),
        required=True,
        min_value=0,
        help_text=_(
            'This email will be sent out this many days before the order expires. If the '
            'value is 0, the mail will never be sent.'
        ),
    )
    mail_text_order_expire_warning = I18nFormField(
        label=_('Text'),
        required=False,
        widget=I18nTextarea,
    )

    mail_text_waiting_list = I18nFormField(
        label=_('Text'),
        required=False,
        widget=I18nTextarea,
    )

    mail_text_order_canceled = I18nFormField(
        label=_('Text'),
        required=False,
        widget=I18nTextarea,
    )

    mail_text_order_custom_mail = I18nFormField(
        label=_('Text'),
        required=False,
        widget=I18nTextarea,
    )

    mail_text_download_reminder = I18nFormField(
        label=_('Text sent to order contact address'),
        required=False,
        widget=I18nTextarea,
    )
    mail_send_download_reminder_attendee = forms.BooleanField(
        label=_('Send an email to attendees'),
        help_text= MAIL_SEND_ORDER_PLACED_ATTENDEE_HELP,
        required=False,
    )
    mail_text_download_reminder_attendee = I18nFormField(
        label=_('Text sent to attendees'),
        required=False,
        widget=I18nTextarea,
    )
    mail_days_download_reminder = forms.IntegerField(
        label=_('Number of days'),
        required=False,
        min_value=0,
        help_text=_(
            'This email will be sent out this many days before the order event starts. If the '
            'field is empty, the mail will never be sent.'
        ),
    )
    mail_sales_channel_download_reminder = forms.MultipleChoiceField(
        choices=lambda: [(ident, sc.verbose_name) for ident, sc in get_all_sales_channels().items()],
        label=_('Sales channels'),
        help_text=_(
            'This email will only be send to orders from these sales channels. The online shop must be enabled.'
        ),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'scrolling-multiple-choice'}),
        validators=[contains_web_channel_validate],
    )

    mail_text_order_placed_require_approval = I18nFormField(
        label=_('Received order'),
        required=False,
        widget=I18nTextarea,
    )
    mail_text_order_approved = I18nFormField(
        label=_('Approved order'),
        required=False,
        widget=I18nTextarea,
        help_text=_(
            'This will only be sent out for non-free orders. Free orders will receive the free order '
            'template from below instead.'
        ),
    )
    mail_text_order_approved_free = I18nFormField(
        label=_('Approved free order'),
        required=False,
        widget=I18nTextarea,
        help_text=_(
            'This will only be sent out for free orders. Non-free orders will receive the non-free order '
            'template from above instead.'
        ),
    )
    mail_text_order_denied = I18nFormField(
        label=_('Denied order'),
        required=False,
        widget=I18nTextarea,
    )

    base_context = {
        'mail_text_order_placed': ['event', 'order', 'payment'],
        'mail_text_order_placed_attendee': ['event', 'order', 'position'],
        'mail_text_order_placed_require_approval': ['event', 'order'],
        'mail_text_order_approved': ['event', 'order'],
        'mail_text_order_approved_free': ['event', 'order'],
        'mail_text_order_denied': ['event', 'order', 'comment'],
        'mail_text_order_paid': ['event', 'order', 'payment_info'],
        'mail_text_order_paid_attendee': ['event', 'order', 'position'],
        'mail_text_order_free': ['event', 'order'],
        'mail_text_order_free_attendee': ['event', 'order', 'position'],
        'mail_text_order_changed': ['event', 'order'],
        'mail_text_order_canceled': ['event', 'order'],
        'mail_text_order_expire_warning': ['event', 'order'],
        'mail_text_order_custom_mail': ['event', 'order'],
        'mail_text_download_reminder': ['event', 'order'],
        'mail_text_download_reminder_attendee': ['event', 'order', 'position'],
        'mail_text_resend_link': ['event', 'order'],
        'mail_text_waiting_list': ['event', 'waiting_list_entry'],
        'mail_text_resend_all_links': ['event', 'orders'],
    }

    def _set_field_placeholders(self, fn, base_parameters):
        phs = ['{%s}' % p for p in sorted(get_available_placeholders(self.event, base_parameters).keys())]
        ht = _('Available placeholders: {list}').format(list=', '.join(phs))
        if self.fields[fn].help_text:
            self.fields[fn].help_text += f' {str(ht)}'
        else:
            self.fields[fn].help_text = ht
        self.fields[fn].validators.append(PlaceholderValidator(phs))

    def __init__(self, *args, **kwargs):
        self.event = kwargs.get('obj')
        super().__init__(*args, **kwargs)
        for k, v in self.base_context.items():
            if k in self.fields:
                self._set_field_placeholders(k, v)


class QueuedMailFilterForm(forms.Form):
    subject = forms.CharField(required=False, label="Subject contains")
    recipient = forms.CharField(required=False, label="Recipient contains")

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop("event", None)
        self.sent = kwargs.pop("sent", None)
        super().__init__(*args, **kwargs)

    def filter_queryset(self, qs):
        if self.cleaned_data.get("subject"):
            qs = qs.filter(subject__icontains=self.cleaned_data["subject"])
        if self.cleaned_data.get("recipient"):
            qs = qs.filter(recipient__icontains=self.cleaned_data["recipient"])
        if self.sent is not None:
            qs = qs.filter(sent=self.sent)
        return qs


class QueuedMailEditForm(forms.ModelForm):
    #
    new_attachment = forms.FileField(
        required=False,
        label="New attachment",
        help_text="Upload a new file to replace the existing one."
    )
    
    class Meta:
        model = QueuedMail
        fields = [
            'recipient',
            'reply_to',
            'bcc',
            'subject',
            'message',
        ]
        labels = {
            'recipient': 'To',
        }
        widgets = {
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'recipient': forms.EmailInput(attrs={'class': 'form-control'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
            'reply_to': forms.TextInput(attrs={'class': 'form-control'}),
            'bcc': forms.Textarea(attrs={'class': 'form-control', 'rows': 1}),
        }

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop('event', None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        instance = super().save(commit=False)

        if self.cleaned_data.get('new_attachment'):
            uploaded_file = self.cleaned_data['new_attachment']
            cf = CachedFile.objects.create(file=uploaded_file, filename=uploaded_file.name)
            instance.attachments = [str(cf.id)]

        if commit:
            instance.save()
        return instance
