from collections import defaultdict

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Exists, OuterRef, Q
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.html import escape
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy
from django_scopes.forms import SafeModelMultipleChoiceField
from i18nfield.forms import I18nFormField, I18nTextarea, I18nTextInput

from eventyay.base.channels import get_all_sales_channels
from eventyay.base.email import get_available_placeholders
from eventyay.mail.context import get_available_placeholders as get_talk_placeholders
from eventyay.base.forms import PlaceholderValidator, SettingsForm
from eventyay.base.forms.widgets import SplitDateTimePickerWidget
from eventyay.base.meetup import is_meetup_event
from eventyay.base.models.auth import User
from eventyay.base.models.base import CachedFile
from eventyay.base.models.checkin import CheckinList
from eventyay.base.models.event import SubEvent
from eventyay.base.models.orders import Order, OrderPosition
from eventyay.base.models.organizer import Team
from eventyay.base.models.product import Product
from eventyay.common.forms.fields import I18nEmailBodyFormField
from eventyay.common.forms.mixins import ScheduledAtValidationMixin
from eventyay.common.forms.renderers import TabularFormRenderer
from eventyay.common.forms.widgets import EnhancedSelect, EnhancedSelectMultiple, I18nEmailEditorWidget
from eventyay.consts import SizeKey
from eventyay.control.forms import CachedFileField, SplitDateTimeField
from eventyay.control.forms.widgets import Select2, Select2Multiple
from eventyay.helpers.timezone import attach_timezone_to_naive_clock_time, get_browser_timezone
from eventyay.orga.forms.mails import TalkSplitDateTimePickerWidget
from eventyay.plugins.sendmail.models import ComposingFor, EmailQueue, EmailQueueToUser


MAIL_SEND_ORDER_PLACED_ATTENDEE_HELP = _( 'If the order contains attendees with email addresses different from the person who orders the ' 'tickets, the following email will be sent out to the attendees.' )

def contains_web_channel_validate(value):
    if 'web' not in value:
        raise ValidationError(_("The 'web' sales channel must be selected."))

RECIPIENTS_DEPENDENCY = 'select[name=recipients]'
RECIPIENTS_INDIVIDUAL = 'individual'


class MailForm(ScheduledAtValidationMixin, forms.Form):
    default_renderer = TabularFormRenderer

    recipients = forms.ChoiceField(
        label=_('Recipients'),
        widget=EnhancedSelect(attrs={'title': _('Recipient type'), 'placeholder': _('Recipient type')}),
        required=True,
        choices=[],
        error_messages={'required': _('Please select a recipient type.')},
    )
    order_status = forms.MultipleChoiceField()  # overridden later
    subject = forms.CharField(label=_('Subject'))
    text = forms.CharField(label=_('Message'))
    reply_to = forms.CharField(
        label=_('Reply-To'),
        required=False,
        help_text=_('Change the Reply-To address if you do not want to use the default organiser address'),
        widget=forms.EmailInput(),
    )
    bcc = forms.CharField(
        label=_('BCC'),
        required=False,
        help_text=_('Enter comma-separated BCC addresses'),
        widget=forms.TextInput(),
    )
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
        max_size=settings.MAX_SIZE_CONFIG[SizeKey.UPLOAD_SIZE_OTHER],
    )  # TODO i18n
    products = forms.ModelMultipleChoiceField(
        widget=EnhancedSelectMultiple(attrs={'title': _('Ticket types'), 'placeholder': _('Ticket types')}),
        label=_('Ticket types'),
        required=False,
        queryset=Product.objects.none(),
    )
    has_filter_checkins = forms.ChoiceField(
        label=_('Check-in filter'),
        choices=[('', _('No filter')), ('yes', _('Yes'))],
        required=False,
        widget=EnhancedSelect(attrs={'title': _('Check-in filter'), 'placeholder': _('Check-in filter')}),
    )
    checkin_lists = SafeModelMultipleChoiceField(
        queryset=CheckinList.objects.none(), required=False
    )  # overridden later
    not_checked_in = forms.ChoiceField(
        label=_('Not checked in'),
        choices=[('', _('No')), ('yes', _('Yes'))],
        required=False,
        widget=EnhancedSelect(attrs={'title': _('Not checked in'), 'placeholder': _('Not checked in')}),
    )
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
    order_created_from = forms.SplitDateTimeField(
        widget=TalkSplitDateTimePickerWidget(),
        label=_('Orders created after'),
        required=False,
    )
    order_created_to = forms.SplitDateTimeField(
        widget=TalkSplitDateTimePickerWidget(),
        label=_('Orders created before'),
        required=False,
    )
    scheduled_at = SplitDateTimeField(
        widget=SplitDateTimePickerWidget(),
        label=_('Send later'),
        required=False,
        help_text=_('Leave empty to send immediately. If set, the email will be sent at this time. Time is interpreted in the event timezone.'),
    )
    test_email = forms.EmailField(
        label=_('Test email address'),
        required=False,
    )
    individual_attendees = SafeModelMultipleChoiceField(
        queryset=Product.objects.none(), required=False
    )
    browser_timezone = forms.CharField(
        widget=forms.HiddenInput(attrs={'class': 'browser-timezone-field'}),
        required=False,
        initial='UTC',
    )

    @cached_property
    def valid_placeholders(self):
        message_placeholders = ['event', 'order', 'position_or_address']
        return get_available_placeholders(self.event, message_placeholders)

    @cached_property
    def grouped_placeholders(self):
        placeholders = self.valid_placeholders
        grouped = defaultdict(list)
        # Ticket placeholders use order/attendee/invoice context, not talk session keys.
        specificity = (
            ('position_or_address', 'ticket'),
            ('position', 'ticket'),
            ('invoice_address', 'invoice'),
            ('order', 'order'),
            ('event', 'event'),
        )
        for placeholder in placeholders.values():
            if getattr(placeholder, 'is_visible', True) is False:
                continue
            placeholder.rendered_sample = escape(placeholder.render_sample(self.event))
            for arg, group in specificity:
                if arg in placeholder.required_context:
                    grouped[group].append(placeholder)
                    break
            else:
                grouped['other'].append(placeholder)
        return grouped

    def clean(self):
        d = super().clean()
        if d is None:
            return d
        d['has_filter_checkins'] = d.get('has_filter_checkins') in ('yes', True)
        d['not_checked_in'] = d.get('not_checked_in') in ('yes', True)
        if self.draft_save:
            return d
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

    def _recipient_dependency_attrs(self, *, individual=False):
        attrs = {'data-display-dependency': RECIPIENTS_DEPENDENCY}
        if individual:
            attrs['data-display-dependency-value'] = RECIPIENTS_INDIVIDUAL
        else:
            attrs['data-display-dependency-value'] = RECIPIENTS_INDIVIDUAL
            attrs['data-inverse'] = 'true'
        return attrs

    def _set_field_placeholders(self, fn, base_parameters):
        """Validate placeholders without rendering the long help-text list (drawer covers that)."""
        phs = [f'{{{p}}}' for p in sorted(get_available_placeholders(self.event, base_parameters).keys())]
        self.fields[fn].validators.append(PlaceholderValidator(phs))

    def __init__(self, *args, **kwargs):
        event = self.event = kwargs.pop('event')
        self.draft_save = kwargs.pop('draft_save', False)
        super().__init__(*args, **kwargs)
        
        self.fields['scheduled_at'].widget.widgets[0].attrs['placeholder'] = ''
        self.fields['scheduled_at'].widget.widgets[1].attrs['placeholder'] = ''

        recp_choices = [('', _('Recipient type'))]
        recp_choices.append(('orders', _('Everyone who created a ticket order')))
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
        recp_choices.append(('individual', _('Specific attendees')))
        self.fields['recipients'].choices = recp_choices
        self.fields['recipients'].initial = ''

        self.fields['subject'] = I18nFormField(
            label=_('Subject'),
            widget=I18nTextInput,
            required=True,
            locales=event.settings.get('locales'),
        )
        message_placeholders = ['event', 'order', 'position_or_address']
        placeholder_names = sorted(get_available_placeholders(self.event, message_placeholders).keys())
        self.fields['text'] = I18nEmailBodyFormField(
            label=_('Message'),
            widget=I18nEmailEditorWidget,
            widget_kwargs={'placeholders': placeholder_names},
            required=True,
            locales=event.settings.get('locales'),
        )
        self._set_field_placeholders('subject', message_placeholders)
        self._set_field_placeholders('text', message_placeholders)
        choices = [(e, l) for e, l in Order.STATUS_CHOICE if e != 'n']
        choices.insert(0, ('na', _('payment pending (except unapproved)')))
        choices.insert(0, ('pa', _('approval pending')))
        if not event.settings.get('payment_term_expire_automatically', as_type=bool):
            choices.append(('overdue', _('pending with payment overdue')))
        self.fields['order_status'] = forms.MultipleChoiceField(
            label=_('Order status'),
            required=False,
            widget=EnhancedSelectMultiple(
                attrs={
                    'title': _('Order statuses'),
                    'placeholder': _('Order statuses'),
                    **self._recipient_dependency_attrs(),
                }
            ),
            choices=choices,
        )
        if self.initial.get('order_status') and 'n' in self.initial['order_status']:
            self.initial['order_status'].append('pa')
            self.initial['order_status'].append('na')

        self.fields['products'].label = _('Ticket types')
        self.fields['products'].queryset = event.products.all()
        self.fields['products'].required = False
        self.fields['products'].widget.attrs.update(
            {'title': _('Ticket types'), **self._recipient_dependency_attrs()}
        )

        self.fields['checkin_lists'].queryset = event.checkin_lists.all()
        self.fields['checkin_lists'].widget = EnhancedSelectMultiple(
            attrs={
                'title': _('Check-in lists'),
                'placeholder': _('Check-in lists'),
                **self._recipient_dependency_attrs(),
            }
        )
        self.fields['checkin_lists'].label = _('Check-in lists')
        self.fields['has_filter_checkins'].widget.attrs.update(
            {'title': _('Check-in filter'), **self._recipient_dependency_attrs()}
        )
        self.fields['not_checked_in'].widget.attrs.update(
            {'title': _('Not checked in'), **self._recipient_dependency_attrs()}
        )

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
                    **self._recipient_dependency_attrs(),
                }
            )
            self.fields['subevent'].widget.choices = self.fields['subevent'].choices
            self.fields['subevents_from'].widget.attrs.update(self._recipient_dependency_attrs())
            self.fields['subevents_to'].widget.attrs.update(self._recipient_dependency_attrs())
        else:
            del self.fields['subevent']
            del self.fields['subevents_from']
            del self.fields['subevents_to']
        self.fields['order_created_from'].widget.attrs.update(self._recipient_dependency_attrs())
        self.fields['order_created_to'].widget.attrs.update(self._recipient_dependency_attrs())

        self.fields['individual_attendees'].queryset = OrderPosition.objects.filter(order__event=event)
        self.fields['individual_attendees'].widget = Select2Multiple(
            attrs={
                'data-model-select2': 'generic',
                'data-select2-url': reverse(
                    'control:event.mail.attendees.select2',
                    kwargs={
                        'event': event.slug,
                        'organizer': event.organizer.slug,
                    },
                ),
                'data-placeholder': _('Search for attendees (name, email, or order code)'),
                **self._recipient_dependency_attrs(individual=True),
            }
        )
        self.fields['individual_attendees'].label = _('Specific attendees')
        self.fields['individual_attendees'].help_text = _(
            'Select attendees that should receive the email regardless of the other filters.'
        )
        self.fields['individual_attendees'].widget.choices = self.fields['individual_attendees'].choices

        for field_name, initial_value in list(self.initial.items()):
            if field_name in ('has_filter_checkins', 'not_checked_in') and isinstance(initial_value, bool):
                self.initial[field_name] = 'yes' if initial_value else ''

        if self.draft_save:
            for field_name in ('recipients', 'order_status', 'products', 'subject', 'text'):
                if field_name in self.fields:
                    self.fields[field_name].required = False

    def resolve_orders(self):
        cleaned = self.cleaned_data
        event = self.event
        if not cleaned.get('recipients'):
            return Order.objects.none()
        if cleaned.get('recipients') == 'individual':
            individual_attendees = cleaned.get('individual_attendees')
            if not individual_attendees:
                return Order.objects.none()
            return Order.objects.filter(event=event, positions__in=individual_attendees).distinct()

        qs = Order.objects.filter(event=event)
        # Only apply status/product defaults once a recipient type is chosen; empty
        # filters must not silently select the whole audience on page load.
        order_status = cleaned.get('order_status') or ['p', 'na']
        statusq = Q(status__in=order_status)
        if 'overdue' in order_status:
            statusq |= Q(status=Order.STATUS_PENDING, expires__lt=now())
        if 'pa' in order_status:
            statusq |= Q(status=Order.STATUS_PENDING, require_approval=True)
        if 'na' in order_status:
            statusq |= Q(status=Order.STATUS_PENDING, require_approval=False)
        orders = qs.filter(statusq)

        products = cleaned.get('products') or list(event.products.all())
        opq = OrderPosition.objects.filter(
            order=OuterRef('pk'),
            canceled=False,
            product_id__in=[p.pk for p in products] if products else [],
        )

        if cleaned.get('has_filter_checkins'):
            ql = []
            if cleaned.get('not_checked_in'):
                ql.append(Q(checkins__list_id=None))
            if cleaned.get('checkin_lists'):
                ql.append(
                    Q(
                        checkins__list_id__in=[i.pk for i in cleaned.get('checkin_lists', [])],
                    )
                )
            if len(ql) == 2:
                opq = opq.filter(ql[0] | ql[1])
            elif ql:
                opq = opq.filter(ql[0])
            else:
                opq = opq.none()

        if cleaned.get('subevent'):
            opq = opq.filter(subevent=cleaned.get('subevent'))
        if cleaned.get('subevents_from'):
            opq = opq.filter(subevent__date_from__gte=cleaned.get('subevents_from'))
        if cleaned.get('subevents_to'):
            opq = opq.filter(subevent__date_from__lt=cleaned.get('subevents_to'))
        if cleaned.get('order_created_from') or cleaned.get('order_created_to'):
            browser_tz = get_browser_timezone(cleaned.get('browser_timezone'))

            def attach_timezone(dt_value):
                return attach_timezone_to_naive_clock_time(dt_value, browser_tz)

            if cleaned.get('order_created_from'):
                opq = opq.filter(order__datetime__gte=attach_timezone(cleaned['order_created_from']))
            if cleaned.get('order_created_to'):
                opq = opq.filter(order__datetime__lt=attach_timezone(cleaned['order_created_to']))

        return orders.annotate(match_pos=Exists(opq)).filter(match_pos=True).distinct()

    def get_recipient_preview(self):
        if not self.cleaned_data.get('recipients'):
            return []
        orders = self.resolve_orders().prefetch_related('positions__product')
        recipients_mode = self.cleaned_data.get('recipients') or 'orders'
        individual_positions = (
            {pos.pk for pos in self.cleaned_data.get('individual_attendees', [])}
            if recipients_mode == 'individual'
            else None
        )
        recipients = {}

        for order in orders:
            order_fallback_needed = False
            attendee_found = False

            for pos in order.positions.all():
                if pos.canceled:
                    continue
                if individual_positions is not None and pos.pk not in individual_positions:
                    continue
                if pos.attendee_email:
                    attendee_found = True
                    email = pos.attendee_email.strip().lower()
                    entry = recipients.setdefault(
                        email,
                        {
                            'name': str(pos.attendee_name_cached or pos.attendee_email),
                            'email': pos.attendee_email,
                            'submissions': [],
                            'directly_selected': recipients_mode == 'individual',
                        },
                    )
                    entry['submissions'].append(
                        {
                            'title': f'{order.code} – {str(pos.product.name)}',
                            'state': str(order.get_status_display()),
                        }
                    )
                else:
                    order_fallback_needed = True

            if (
                order_fallback_needed
                and not attendee_found
                and recipients_mode == 'attendees'
                and order.email
            ):
                email = order.email.strip().lower()
                recipients.setdefault(
                    email,
                    {
                        'name': order.email,
                        'email': order.email,
                        'submissions': [],
                        'directly_selected': False,
                    },
                )['submissions'].append(
                    {
                        'title': order.code,
                        'state': str(order.get_status_display()),
                    }
                )

            if recipients_mode in ('both', 'orders') and order.email:
                email = order.email.strip().lower()
                entry = recipients.setdefault(
                    email,
                    {
                        'name': order.email,
                        'email': order.email,
                        'submissions': [],
                        'directly_selected': False,
                    },
                )
                if not any(item['title'].startswith(order.code) for item in entry['submissions']):
                    entry['submissions'].append(
                        {
                            'title': order.code,
                            'state': str(order.get_status_display()),
                        }
                    )

        return sorted(recipients.values(), key=lambda recipient: recipient['email'])


class TicketMailRecipientsForm(MailForm):
    """Audience preview variant of the ticket mail form."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('subject', 'text', 'attachment', 'reply_to', 'bcc', 'scheduled_at', 'test_email'):
            self.fields.pop(name, None)
        self.fields['products'].required = False
        # Audience preview may load before a recipient type is chosen.
        self.fields['recipients'].required = False
        self.fields['recipients'].initial = ''

    def clean(self):
        # Preview may load with no audience chosen yet; send still requires recipients.
        d = forms.Form.clean(self)
        if d is None:
            return d
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
        d['has_filter_checkins'] = d.get('has_filter_checkins') == 'yes'
        d['not_checked_in'] = d.get('not_checked_in') == 'yes'
        return d


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

    mail_text_meetup_registration = I18nFormField(
        label=_('Text sent to registration contact address'),
        required=False,
        widget=I18nTextarea,
    )
    mail_send_meetup_registration_attendee = forms.BooleanField(
        label=_('Send an email to attendees'),
        help_text=MAIL_SEND_ORDER_PLACED_ATTENDEE_HELP,
        required=False,
    )
    mail_text_meetup_registration_attendee = I18nFormField(
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
        'mail_text_meetup_registration': ['event', 'order'],
        'mail_text_meetup_registration_attendee': ['event', 'order', 'position'],
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
        self.base_context = dict(self.base_context)

        if not is_meetup_event(self.event):
            for field in ('mail_text_meetup_registration', 'mail_send_meetup_registration_attendee',
                          'mail_text_meetup_registration_attendee'):
                self.fields.pop(field, None)
                self.base_context.pop(field, None)

        for k, v in self.base_context.items():
            if k in self.fields:
                self._set_field_placeholders(k, v)


class EmailQueueEditForm(ScheduledAtValidationMixin, forms.ModelForm):
    new_attachment = forms.FileField(
        required=False,
        label=_("New attachment"),
        help_text=_("Upload a new file to replace the existing one.")
    )

    emails = forms.CharField(
        label=_("Recipients"),
        help_text=_("Edit the list of recipient email addresses separated by commas."),
        required=True,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'})
    )

    class Meta:
        model = EmailQueue
        fields = [
            'reply_to',
            'bcc',
            'scheduled_at',
        ]
        field_classes = {
            'scheduled_at': SplitDateTimeField,
        }
        labels = {
            'reply_to': _('Reply-To'),
            'bcc': _('BCC'),
            'scheduled_at': _('Send later'),
        }
        help_texts = {
            'reply_to': _("Any changes to the Reply-To field apply only to this queued email. If left empty, the event's default Reply-To will be used."),
            'bcc': _("Any changes to the BCC field will apply only to this queued email."),
            'scheduled_at': _("Leave empty to send immediately. If set, the email will be sent at this time."),
        }
        widgets = {
            'reply_to': forms.TextInput(attrs={'class': 'form-control'}),
            'bcc': forms.Textarea(attrs={'class': 'form-control', 'rows': 1}),
            'scheduled_at': SplitDateTimePickerWidget(),
        }

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop('event', None)
        self.read_only = kwargs.pop('read_only', False)
        super().__init__(*args, **kwargs)

        if self.instance.composing_for == ComposingFor.TEAMS:
            base_placeholders = ['event', 'user', 'team']
            base_ph = get_available_placeholders(self.event, base_placeholders)
            talk_ph = get_talk_placeholders(self.event, base_placeholders)
            placeholder_names = sorted({**base_ph, **talk_ph}.keys())
        else:
            base_placeholders = ['event', 'order', 'position_or_address']
            placeholder_names = sorted(get_available_placeholders(self.event, base_placeholders).keys())

        existing_recipients = EmailQueueToUser.objects.filter(mail=self.instance).order_by('id')
        self.recipient_objects = list(existing_recipients)
        self.fields['emails'].initial = ", ".join([u.email for u in self.recipient_objects])

        saved_locales = set()
        if self.instance.subject and hasattr(self.instance.subject, '_data'):
            saved_locales |= set(self.instance.subject._data.keys())
        if self.instance.message and hasattr(self.instance.message, '_data'):
            saved_locales |= set(self.instance.message._data.keys())

        configured_locales = set(self.event.settings.get('locales', [])) if self.event else set()
        allowed_locales = saved_locales | configured_locales

        self.fields['subject'] = I18nFormField(
            label=_('Subject'),
            widget=I18nTextInput,
            required=False,
            locales=list(allowed_locales),
            initial=self.instance.subject
        )
        self.fields['text'] = I18nEmailBodyFormField(
            label=_('Message'),
            widget=I18nEmailEditorWidget,
            widget_kwargs={'placeholders': placeholder_names},
            required=False,
            locales=list(allowed_locales),
            initial=self.instance.message,
        )

        if not self.read_only:
            self._set_field_placeholders('subject', base_placeholders)
            self._set_field_placeholders('text', base_placeholders)

    def _set_field_placeholders(self, fn, base_parameters):
        if self.instance.composing_for == ComposingFor.TEAMS:
            base_ph = get_available_placeholders(self.event, base_parameters)
            talk_ph = get_talk_placeholders(self.event, base_parameters)
            all_ph = {**base_ph, **talk_ph}
            phs = ['{%s}' % p for p in sorted(all_ph.keys())]
        else:
            phs = ['{%s}' % p for p in sorted(get_available_placeholders(self.event, base_parameters).keys())]
        ht = _('Available placeholders: {list}').format(list=', '.join(phs))
        if self.fields[fn].help_text:
            self.fields[fn].help_text += ' ' + str(ht)
        else:
            self.fields[fn].help_text = ht
        self.fields[fn].validators.append(PlaceholderValidator(phs))

    def clean_emails(self):
        updated_emails = [
            email.strip()
            for email in self.cleaned_data['emails'].split(',')
            if email.strip()
        ]

        if len(updated_emails) == 0:
            raise ValidationError(
                _("At least one recipient must remain. You cannot remove all recipients.")
            )

        if len(updated_emails) != len(self.recipient_objects):
            raise ValidationError(
                _("You cannot add new recipients or remove recipients. Only editing existing email addresses is allowed.")
            )

        return updated_emails

    def save(self, commit=True):
        instance = super().save(commit=False)

        updated_emails = self.cleaned_data['emails']

        for i, email in enumerate(updated_emails):
            self.recipient_objects[i].email = email
            if commit:
                self.recipient_objects[i].save()

        # Handle new attachment
        if self.cleaned_data.get('new_attachment'):
            uploaded_file = self.cleaned_data['new_attachment']
            cf = CachedFile.objects.create(file=uploaded_file, filename=uploaded_file.name)
            instance.attachments = [cf.id]

        instance.subject = self.cleaned_data['subject']
        instance.message = self.cleaned_data['text']

        if commit:
            instance.save()

        return instance


class TeamMailForm(ScheduledAtValidationMixin, forms.Form):
    subject = forms.CharField(label=_('Subject'))
    message = forms.CharField(label=_('Message'))
    attachment = CachedFileField(
        label=_('Attachment'),
        required=False,
        ext_whitelist=(
            '.png', '.jpg', '.gif', '.jpeg', '.pdf', '.txt', '.docx', '.svg', '.pptx',
            '.ppt', '.doc', '.xlsx', '.xls', '.jfif', '.heic', '.heif', '.pages', '.bmp',
            '.tif', '.tiff',
        ),
        help_text=_(
            'Sending an attachment increases the chance of your email not arriving or being sorted into spam folders. '
            'We recommend only using PDFs of no more than 2 MB in size.'
        ),
        max_size=settings.MAX_SIZE_CONFIG[SizeKey.UPLOAD_SIZE_ATTACHMENT],
    )

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop('event')
        self.draft_save = kwargs.pop('draft_save', False)
        super().__init__(*args, **kwargs)

        locales = self.event.settings.get('locales') or [self.event.locale or 'en']
        if isinstance(locales, str):
            locales = [locales]

        team_placeholders = ['event', 'user', 'team']
        base_ph = get_available_placeholders(self.event, team_placeholders)
        talk_ph = get_talk_placeholders(self.event, team_placeholders)
        self.valid_placeholders = {**base_ph, **talk_ph}
        placeholder_names = sorted(self.valid_placeholders.keys())
        placeholder_text = _("Available placeholders: ") + ', '.join(f"{{{key}}}" for key in placeholder_names)

        self.fields['subject'] = I18nFormField(
            label=_('Subject'),
            widget=I18nTextInput,
            required=True,
            locales=locales,

        )
        self.fields['message'] = I18nEmailBodyFormField(
            label=_('Message'),
            widget=I18nEmailEditorWidget,
            widget_kwargs={'placeholders': placeholder_names},
            required=True,
            locales=locales
        )

        self.fields['teams'] = forms.ModelMultipleChoiceField(
            queryset=Team.objects.filter(organizer=self.event.organizer),
            widget=EnhancedSelectMultiple(attrs={'title': _('All teams'), 'placeholder': _('All teams')}),
            label=_("Team"),
            required=False
        )
        self.fields['team_role'] = forms.ChoiceField(
            label=_('Team role'),
            required=False,
            choices=[('', _('All team roles'))] + Team.TEAMSHIFTS_ROLE_CHOICES,
            widget=EnhancedSelect(attrs={'title': _('All team roles'), 'placeholder': _('All team roles')}),
        )
        permission_choices = [('', _('All permission levels'))]
        for p in Team._permission_field_names():
            verbose_name = Team._meta.get_field(p).verbose_name
            permission_choices.append((p, verbose_name))
        
        self.fields['permission_level'] = forms.ChoiceField(
            label=_('Permission level'),
            required=False,
            choices=permission_choices,
            widget=EnhancedSelect(attrs={'title': _('All permission levels'), 'placeholder': _('All permission levels')}),
        )

        self.fields['status'] = forms.ChoiceField(
            label=_('Status'),
            required=False,
            choices=[('', _('Any')), ('active', _('Active')), ('inactive', _('Inactive'))],
            widget=EnhancedSelect(attrs={'title': _('Any'), 'placeholder': _('Any')}),
            initial='active',
        )

        users_qs = User.objects.filter(teams__organizer=self.event.organizer).distinct()
        self.fields['specific_people'] = forms.ModelMultipleChoiceField(
            queryset=users_qs,
            label=_('Specific people'),
            required=False,
            widget=EnhancedSelectMultiple(attrs={'title': _('All people'), 'placeholder': _('All people')}),
        )
        self.fields['exclude_me'] = forms.BooleanField(
            label=_('Do not include me in recipients'),
            required=False,
        )
        self.fields['reply_to'] = forms.CharField(
            label=_('Reply-To'),
            required=False,
            help_text=_('Change the Reply-To address if you do not want to use the default organiser address'),
            widget=forms.EmailInput(),
        )
        self.fields['bcc'] = forms.CharField(
            label=_('BCC'),
            required=False,
            help_text=_('Enter comma-separated BCC addresses'),
            widget=forms.TextInput(),
        )
        self.fields['test_email'] = forms.EmailField(
            label=_('Test email address'),
            required=False,
        )
        
        widget = SplitDateTimePickerWidget()
        widget.widgets[0].attrs['placeholder'] = ''
        widget.widgets[1].attrs['placeholder'] = ''
        self.fields['scheduled_at'] = SplitDateTimeField(
            widget=widget,
            label=_('Send later'),
            required=False,
            help_text=_('Leave empty to send immediately. If set, the email will be sent at this time. Time is interpreted in the event timezone.'),
        )

        if self.draft_save:
            for field_name in ('teams', 'subject', 'message'):
                self.fields[field_name].required = False

    @cached_property
    def grouped_placeholders(self):
        placeholders = self.valid_placeholders
        grouped = defaultdict(list)
        specificity = (
            ('user', 'user'),
            ('team', 'user'),
            ('event', 'event'),
        )
        for placeholder in placeholders.values():
            if getattr(placeholder, 'is_visible', True) is False:
                continue
            placeholder.rendered_sample = escape(placeholder.render_sample(self.event))
            for arg, group in specificity:
                if arg in placeholder.required_context:
                    grouped[group].append(placeholder)
                    break
            else:
                grouped['other'].append(placeholder)
        return grouped

    def get_recipient_preview(self, user=None):
        recipients = {}
        team_role = self.cleaned_data.get('team_role')
        teams = self.cleaned_data.get('teams')
        permission_level = self.cleaned_data.get('permission_level')
        status = self.cleaned_data.get('status')
        specific_people = self.cleaned_data.get('specific_people')
        exclude_me = self.cleaned_data.get('exclude_me')
        
        # Build queryset
        team_filters = {'teams__organizer': self.event.organizer}
        if teams:
            team_filters['teams__in'] = teams
        if team_role:
            team_filters['teams__teamshifts_role'] = team_role
        if permission_level:
            team_filters[f'teams__{permission_level}'] = True

        qs = User.objects.filter(**team_filters)
        if status == 'active':
            qs = qs.filter(is_active=True)
        elif status == 'inactive':
            qs = qs.filter(is_active=False)
        if specific_people:
            qs = qs.filter(pk__in=specific_people)
        if exclude_me and user:
            qs = qs.exclude(pk=user.pk)
            
        qs = qs.distinct()
        
        for u in qs:
            if not u.email:
                continue
                
            user_teams = u.teams.filter(organizer=self.event.organizer)
            member_teams = list(user_teams.values_list('name', flat=True))
            roles = [r for r in user_teams.values_list('teamshifts_role', flat=True) if r]
            permissions = []
            for t in user_teams:
                for p in t._permission_field_names():
                    if getattr(t, p):
                        verbose_name = str(t._meta.get_field(p).verbose_name)
                        if verbose_name not in permissions:
                            permissions.append(verbose_name)
                            
            if specific_people and u.pk in specific_people.values_list('pk', flat=True):
                from django.utils.translation import gettext_lazy as _
                reason = str(_("Selected directly"))
            else:
                from django.utils.translation import gettext_lazy as _
                reason = str(_("Matched filters"))

            recipients[u.email] = {
                'name': u.fullname or u.email,
                'email': u.email,
                'team': ', '.join(member_teams),
                'role': ', '.join(roles),
                'permission_level': ', '.join(permissions) if permissions else '',
                'status': 'Active' if u.is_active else 'Inactive',
                'reason_included': reason,
            }
            
        return sorted(recipients.values(), key=lambda r: r['email'])


class TeamMailRecipientsForm(TeamMailForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('subject', 'message', 'attachment', 'reply_to', 'bcc', 'scheduled_at', 'test_email'):
            self.fields.pop(name, None)
