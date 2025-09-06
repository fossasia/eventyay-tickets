import inspect
import logging
import os
import secrets
from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from email import policy
from email.parser import BytesParser
from itertools import groupby
from pathlib import Path
from smtplib import SMTPResponseException

from css_inline import inline as inline_css
from django.conf import settings
from django.core.mail.backends.filebased import EmailBackend as _FileBasedEmailBackend
from django.core.mail.backends.smtp import EmailBackend
from django.core.mail.message import EmailMessage
from django.db.models import Count
from django.dispatch import receiver
from django.template.loader import get_template
from django.utils.timezone import now as djnow
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Attachment, Bcc, Mail

from eventyay.base.i18n import (
    LazyCurrencyNumber,
    LazyDate,
    LazyExpiresDate,
    LazyNumber,
)
from eventyay.base.models import Event
from eventyay.base.settings import PERSON_NAME_SCHEMES
from eventyay.base.signals import (
    register_html_mail_renderers,
    register_mail_placeholders,
)
from eventyay.base.templatetags.rich_text import markdown_compile_email

logger = logging.getLogger(__name__)


class SendGridEmail:
    api_key = ''

    def __init__(self, api_key):
        self.api_key = api_key

    def test(self, from_addr):
        message = Mail(
            from_email=from_addr,
            to_emails='testdummy@eventyay.com',
            subject='Eventyay test email',
            html_content='Eventyay test email',
        )
        sg = SendGridAPIClient(self.api_key)
        sg.send(message)

    def bytes_to_base64_string(self, value: bytes) -> str:
        import base64

        return base64.b64encode(value).decode('ASCII')

    def build_attachment(self, input):
        attachment = Attachment()
        attachment.file_content = self.bytes_to_base64_string(input[1])
        attachment.file_type = input[2]
        attachment.file_name = input[0]
        attachment.disposition = 'attachment'
        # attachment.content_id = "Balance Sheet"
        return attachment

    def send_messages(self, emails):
        for email in emails:
            html_content = None
            try:
                message_context = email.message().as_bytes(linesep='\r\n')
                msg = BytesParser(policy=policy.default).parsebytes(message_context)
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get('Content-Disposition'))

                    if content_type == 'text/html' and 'attachment' not in content_disposition:
                        html_content = part.get_payload(decode=True).decode(part.get_content_charset())
                        break  # Found the HTML content, no need to continue
            except Exception as e:
                logger.error('Error happened when trying to parse mail template: %s' % e)
                html_content = email.body
            message = Mail(
                from_email=email.from_email,
                to_emails=email.to,
                subject=email.subject,
                html_content=html_content,
            )
            sg = SendGridAPIClient(self.api_key)
            bcc = []
            for mail in email.bcc:
                bcc.append(Bcc(mail))
            message.bcc = bcc
            attachments = []
            for attachment in email.attachments:
                attachments.append(self.build_attachment(attachment))

            message.attachment = attachments
            sg.send(message)


class CustomSMTPBackend(EmailBackend):
    def test(self, from_addr):
        try:
            self.open()
            self.connection.ehlo_or_helo_if_needed()
            (code, resp) = self.connection.mail(from_addr, [])
            if code != 250:
                logger.warn('Error testing mail settings, code %d, resp: %s' % (code, resp))
                raise SMTPResponseException(code, resp)
            (code, resp) = self.connection.rcpt('test@eventyay.com')
            if (code != 250) and (code != 251):
                logger.warn('Error testing mail settings, code %d, resp: %s' % (code, resp))
                raise SMTPResponseException(code, resp)
        finally:
            self.close()


class FileSavedEmailBackend(_FileBasedEmailBackend):
    """
    Custom email backend to save emails to a file, instead of sending out to Internet.
    Used for development and testing.

    It is based on Django's file-based email backend, but is customized to:
    - Save in subdirectories by date. It is because we have a feature to send bulk emails,
    it will be difficult to find them with original file-based backend.
    The subdirectory name scheme is: YYYY/mm/DD/HH-MM, it is "per minute" because in development,
    we may try many times in an hour.
    - Save the file with .eml extension, so that it can be opened by email clients (Thunderbird).
    """

    def get_subdir_path(self) -> Path:
        """Get the subdirectory path to save email files."""
        # We use local time, because this backend is only for development and testing.
        # Note that, Django rewrote the `TZ` environment variable, so the time returned by
        # `datetime.now()` may not match your wall clock.
        now = datetime.now()
        return (
            Path(self.file_path).resolve()
            / f'{now.year}'
            / f'{now.month:02}'
            / f'{now.day:02}'
            / f'{now.hour:02}-{now.minute:02}'
        )

    def send_messages(self, email_messages: Sequence[EmailMessage]) -> int:
        """
        Send one or more EmailMessage objects and return the number of email

        Override to create subdirectories before saving the email files.
        """
        if not email_messages:
            return 0
        # Create subdirectory by date
        subdir = self.get_subdir_path()
        os.makedirs(subdir, exist_ok=True)
        n = super().send_messages(email_messages)
        logger.info('Wrote %d email(s) to %s.', n, subdir.relative_to(Path.cwd()))
        return n

    def _get_filename(self):
        """Return a unique file name with .eml extension."""
        if self._fname is None:
            subdir = self.get_subdir_path()
            # We use local time, because this backend is only for development and testing.
            now = datetime.now()
            file_name = f'{now:%Y%m%d-%H%M%S}-{abs(id(self))}.eml'
            self._fname = str(subdir / file_name)
        return self._fname


class BaseHTMLMailRenderer:
    """
    This is the base class for all HTML e-mail renderers.
    """

    def __init__(self, event: Event, organizer=None):
        self.event = event
        self.organizer = organizer

    def __str__(self):
        return self.identifier

    def render(
        self,
        plain_body: str,
        plain_signature: str,
        subject: str,
        order=None,
        position=None,
    ) -> str:
        """
        This method should generate the HTML part of the email.

        :param plain_body: The body of the email in plain text.
        :param plain_signature: The signature with event organizer contact details in plain text.
        :param subject: The email subject.
        :param order: The order if this email is connected to one, otherwise ``None``.
        :param position: The order position if this email is connected to one, otherwise ``None``.
        :return: An HTML string
        """
        raise NotImplementedError()

    @property
    def verbose_name(self) -> str:
        """
        A human-readable name for this renderer. This should be short but self-explanatory.
        """
        raise NotImplementedError()  # NOQA

    @property
    def identifier(self) -> str:
        """
        A short and unique identifier for this renderer.
        This should only contain lowercase letters and in most cases will be the same as your package name or prefixed
        with your package name.
        """
        raise NotImplementedError()  # NOQA

    @property
    def thumbnail_filename(self) -> str:
        """
        A file name discoverable in the static file storage that contains a preview of your renderer. This should
        be with aspect resolution 4:3.
        """
        raise NotImplementedError()  # NOQA

    @property
    def is_available(self) -> bool:
        """
        This renderer will only be available if this returns ``True``. You can use this to limit this renderer
        to certain events. Defaults to ``True``.
        """
        return True


class TemplateBasedMailRenderer(BaseHTMLMailRenderer):
    @property
    def template_name(self):
        raise NotImplementedError()

    def render(self, plain_body: str, plain_signature: str, subject: str, order, position) -> str:
        body_md = markdown_compile_email(plain_body)
        htmlctx = {
            'site': settings.INSTANCE_NAME,
            'site_url': settings.SITE_URL,
            'body': body_md,
            'subject': str(subject),
            'color': settings.EVENTYAY_PRIMARY_COLOR,
            'rtl': get_language() in settings.LANGUAGES_RTL or get_language().split('-')[0] in settings.LANGUAGES_RTL,
        }
        if self.organizer:
            htmlctx['organizer'] = self.organizer

        if self.event:
            htmlctx['event'] = self.event
            htmlctx['color'] = self.event.settings.primary_color

        if plain_signature:
            signature_md = plain_signature.replace('\n', '<br>\n')
            signature_md = markdown_compile_email(signature_md)
            htmlctx['signature'] = signature_md

        if order:
            htmlctx['order'] = order
            positions = list(
                order.positions.select_related('item', 'variation', 'subevent', 'addon_to').annotate(
                    has_addons=Count('addons')
                )
            )
            htmlctx['cart'] = [
                (k, list(v))
                for k, v in groupby(
                    positions,
                    key=lambda op: (
                        op.item,
                        op.variation,
                        op.subevent,
                        op.attendee_name,
                        (op.pk if op.addon_to_id else None),
                        (op.pk if op.has_addons else None),
                    ),
                )
            ]

        if position:
            htmlctx['position'] = position
            htmlctx['ev'] = position.subevent or self.event

        tpl = get_template(self.template_name)
        body_html = inline_css(tpl.render(htmlctx))
        return body_html


class ClassicMailRenderer(TemplateBasedMailRenderer):
    verbose_name = _('Default')
    identifier = 'classic'
    thumbnail_filename = 'eventyay/email/thumb.png'
    template_name = 'eventyay/email/plainwrapper.jinja'


class UnembellishedMailRenderer(TemplateBasedMailRenderer):
    verbose_name = _('Simple with logo')
    identifier = 'simple_logo'
    thumbnail_filename = 'eventyay/email/thumb_simple_logo.png'
    template_name = 'eventyay/email/simple_logo.jinja'


@receiver(register_html_mail_renderers, dispatch_uid='eventyay_email_renderers')
def base_renderers(sender, **kwargs):
    return [ClassicMailRenderer, UnembellishedMailRenderer]


class BaseMailTextPlaceholder:
    """
    This is the base class for for all email text placeholders.
    """

    @property
    def required_context(self):
        """
        This property should return a list of all attribute names that need to be
        contained in the base context so that this placeholder is available. By default,
        it returns a list containing the string "event".
        """
        return ['event']

    @property
    def identifier(self):
        """
        This should return the identifier of this placeholder in the email.
        """
        raise NotImplementedError()

    def render(self, context):
        """
        This method is called to generate the actual text that is being
        used in the email. You will be passed a context dictionary with the
        base context attributes specified in ``required_context``. You are
        expected to return a plain-text string.
        """
        raise NotImplementedError()

    def render_sample(self, event):
        """
        This method is called to generate a text to be used in email previews.
        This may only depend on the event.
        """
        raise NotImplementedError()


class SimpleFunctionalMailTextPlaceholder(BaseMailTextPlaceholder):
    def __init__(self, identifier, args, func, sample):
        self._identifier = identifier
        self._args = args
        self._func = func
        self._sample = sample

    @property
    def identifier(self):
        return self._identifier

    @property
    def required_context(self):
        return self._args

    def render(self, context):
        return self._func(**{k: context[k] for k in self._args})

    def render_sample(self, event):
        if callable(self._sample):
            return self._sample(event)
        else:
            return self._sample


def get_available_placeholders(event, base_parameters):
    if 'order' in base_parameters:
        base_parameters.append('invoice_address')
        base_parameters.append('position_or_address')
    params = {}
    for r, val in register_mail_placeholders.send(sender=event):
        if not isinstance(val, (list, tuple)):
            val = [val]
        for v in val:
            if all(rp in base_parameters for rp in v.required_context):
                params[v.identifier] = v
    return params


def get_email_context(**kwargs):
    from eventyay.base.models import InvoiceAddress

    event = kwargs['event']
    if 'position' in kwargs:
        kwargs.setdefault('position_or_address', kwargs['position'])
    if 'order' in kwargs:
        try:
            kwargs['invoice_address'] = kwargs['order'].invoice_address
        except InvoiceAddress.DoesNotExist:
            kwargs['invoice_address'] = InvoiceAddress(order=kwargs['order'])
        finally:
            kwargs.setdefault('position_or_address', kwargs['invoice_address'])
    ctx = {}
    for r, val in register_mail_placeholders.send(sender=event):
        if not isinstance(val, (list, tuple)):
            val = [val]
        for v in val:
            if all(rp in kwargs for rp in v.required_context):
                ctx[v.identifier] = v.render(kwargs)
    return ctx


def _placeholder_payment(order, payment):
    if not payment:
        return None
    if 'payment' in inspect.signature(payment.payment_provider.order_pending_mail_render).parameters:
        return str(payment.payment_provider.order_pending_mail_render(order, payment))
    else:
        return str(payment.payment_provider.order_pending_mail_render(order))


def get_best_name(position_or_address, parts=False):
    """
    Return the best name we got for either an invoice address or an order position, falling back to the respective other
    """
    from eventyay.base.models import InvoiceAddress, OrderPosition

    if isinstance(position_or_address, InvoiceAddress):
        if position_or_address.name:
            return position_or_address.name_parts if parts else position_or_address.name
        elif position_or_address.order:
            position_or_address = (
                position_or_address.order.positions.exclude(attendee_name_cached='')
                .exclude(attendee_name_cached__isnull=True)
                .first()
            )

    if isinstance(position_or_address, OrderPosition):
        if position_or_address.attendee_name:
            return position_or_address.attendee_name_parts if parts else position_or_address.attendee_name
        elif position_or_address.order:
            try:
                return (
                    position_or_address.order.invoice_address.name_parts
                    if parts
                    else position_or_address.order.invoice_address.name
                )
            except InvoiceAddress.DoesNotExist:
                pass

    return {} if parts else ''


def generate_sample_video_url():
    sample_token = secrets.token_urlsafe(16)
    return '{}/#token={}'.format(settings.SITE_URL, sample_token)


@receiver(register_mail_placeholders, dispatch_uid='pretixbase_register_mail_placeholders')
def base_placeholders(sender, **kwargs):
    from eventyay.multidomain.urlreverse import (
        build_absolute_uri,
        build_join_video_url,
    )

    ph = [
        SimpleFunctionalMailTextPlaceholder('event', ['event'], lambda event: event.name, lambda event: event.name),
        SimpleFunctionalMailTextPlaceholder(
            'event',
            ['event_or_subevent'],
            lambda event_or_subevent: event_or_subevent.name,
            lambda event_or_subevent: event_or_subevent.name,
        ),
        SimpleFunctionalMailTextPlaceholder(
            'event_slug', ['event'], lambda event: event.slug, lambda event: event.slug
        ),
        SimpleFunctionalMailTextPlaceholder('code', ['order'], lambda order: order.code, 'F8VVL'),
        SimpleFunctionalMailTextPlaceholder(
            'total',
            ['order'],
            lambda order: LazyNumber(order.total),
            lambda event: LazyNumber(Decimal('42.23')),
        ),
        SimpleFunctionalMailTextPlaceholder(
            'currency',
            ['event'],
            lambda event: event.currency,
            lambda event: event.currency,
        ),
        SimpleFunctionalMailTextPlaceholder(
            'refund_amount',
            ['event_or_subevent', 'refund_amount'],
            lambda event_or_subevent, refund_amount: LazyCurrencyNumber(refund_amount, event_or_subevent.currency),
            lambda event_or_subevent: LazyCurrencyNumber(Decimal('42.23'), event_or_subevent.currency),
        ),
        SimpleFunctionalMailTextPlaceholder(
            'total_with_currency',
            ['event', 'order'],
            lambda event, order: LazyCurrencyNumber(order.total, event.currency),
            lambda event: LazyCurrencyNumber(Decimal('42.23'), event.currency),
        ),
        SimpleFunctionalMailTextPlaceholder(
            'expire_date',
            ['event', 'order'],
            lambda event, order: LazyExpiresDate(order.expires.astimezone(event.timezone)),
            lambda event: LazyDate(djnow() + timedelta(days=15)),
        ),
        SimpleFunctionalMailTextPlaceholder(
            'url',
            ['order', 'event'],
            lambda order, event: build_absolute_uri(
                event,
                'presale:event.order.open',
                kwargs={
                    'order': order.code,
                    'secret': order.secret,
                    'hash': order.email_confirm_hash(),
                },
            ),
            lambda event: build_absolute_uri(
                event,
                'presale:event.order.open',
                kwargs={
                    'order': 'F8VVL',
                    'secret': '6zzjnumtsx136ddy',
                    'hash': '98kusd8ofsj8dnkd',
                },
            ),
        ),
        SimpleFunctionalMailTextPlaceholder(
            'url_info_change',
            ['order', 'event'],
            lambda order, event: build_absolute_uri(
                event,
                'presale:event.order.modify',
                kwargs={
                    'order': order.code,
                    'secret': order.secret,
                },
            ),
            lambda event: build_absolute_uri(
                event,
                'presale:event.order.modify',
                kwargs={
                    'order': 'F8VVL',
                    'secret': '6zzjnumtsx136ddy',
                },
            ),
        ),
        SimpleFunctionalMailTextPlaceholder(
            'url_products_change',
            ['order', 'event'],
            lambda order, event: build_absolute_uri(
                event,
                'presale:event.order.change',
                kwargs={
                    'order': order.code,
                    'secret': order.secret,
                },
            ),
            lambda event: build_absolute_uri(
                event,
                'presale:event.order.change',
                kwargs={
                    'order': 'F8VVL',
                    'secret': '6zzjnumtsx136ddy',
                },
            ),
        ),
        SimpleFunctionalMailTextPlaceholder(
            'url_cancel',
            ['order', 'event'],
            lambda order, event: build_absolute_uri(
                event,
                'presale:event.order.cancel',
                kwargs={
                    'order': order.code,
                    'secret': order.secret,
                },
            ),
            lambda event: build_absolute_uri(
                event,
                'presale:event.order.cancel',
                kwargs={
                    'order': 'F8VVL',
                    'secret': '6zzjnumtsx136ddy',
                },
            ),
        ),
        SimpleFunctionalMailTextPlaceholder(
            'url',
            ['event', 'position'],
            lambda event, position: build_absolute_uri(
                event,
                'presale:event.order.position',
                kwargs={
                    'order': position.order.code,
                    'secret': position.web_secret,
                    'position': position.positionid,
                },
            ),
            lambda event: build_absolute_uri(
                event,
                'presale:event.order.position',
                kwargs={
                    'order': 'F8VVL',
                    'secret': '6zzjnumtsx136ddy',
                    'position': '123',
                },
            ),
        ),
        SimpleFunctionalMailTextPlaceholder(
            'url',
            ['waiting_list_entry', 'event'],
            lambda waiting_list_entry, event: build_absolute_uri(event, 'presale:event.redeem')
            + '?voucher='
            + waiting_list_entry.voucher.code,
            lambda event: build_absolute_uri(
                event,
                'presale:event.redeem',
            )
            + '?voucher=68CYU2H6ZTP3WLK5',
        ),
        SimpleFunctionalMailTextPlaceholder(
            'invoice_name',
            ['invoice_address'],
            lambda invoice_address: invoice_address.name or '',
            _('John Doe'),
        ),
        SimpleFunctionalMailTextPlaceholder(
            'invoice_company',
            ['invoice_address'],
            lambda invoice_address: invoice_address.company or '',
            _('Sample Corporation'),
        ),
        SimpleFunctionalMailTextPlaceholder(
            'orders',
            ['event', 'orders'],
            lambda event, orders: '\n'
            + '\n\n'.join(
                '* {} - {}'.format(
                    order.full_code,
                    build_absolute_uri(
                        event,
                        'presale:event.order.open',
                        kwargs={
                            'event': event.slug,
                            'organizer': event.organizer.slug,
                            'order': order.code,
                            'secret': order.secret,
                            'hash': order.email_confirm_hash(),
                        },
                    ),
                )
                for order in orders
            ),
            lambda event: '\n'
            + '\n\n'.join(
                '* {} - {}'.format(
                    '{}-{}'.format(event.slug.upper(), order['code']),
                    build_absolute_uri(
                        event,
                        'presale:event.order.open',
                        kwargs={
                            'event': event.slug,
                            'organizer': event.organizer.slug,
                            'order': order['code'],
                            'secret': order['secret'],
                            'hash': order['hash'],
                        },
                    ),
                )
                for order in [
                    {
                        'code': 'F8VVL',
                        'secret': '6zzjnumtsx136ddy',
                        'hash': 'abcdefghi',
                    },
                    {
                        'code': 'HIDHK',
                        'secret': '98kusd8ofsj8dnkd',
                        'hash': 'jklmnopqr',
                    },
                    {
                        'code': 'OPKSB',
                        'secret': '09pjdksflosk3njd',
                        'hash': 'stuvwxy2z',
                    },
                ]
            ),
        ),
        SimpleFunctionalMailTextPlaceholder(
            'hours',
            ['event', 'waiting_list_entry'],
            lambda event, waiting_list_entry: event.settings.waiting_list_hours,
            lambda event: event.settings.waiting_list_hours,
        ),
        SimpleFunctionalMailTextPlaceholder(
            'product',
            ['waiting_list_entry'],
            lambda waiting_list_entry: waiting_list_entry.item.name,
            _('Sample Admission Ticket'),
        ),
        SimpleFunctionalMailTextPlaceholder(
            'code',
            ['waiting_list_entry'],
            lambda waiting_list_entry: waiting_list_entry.voucher.code,
            '68CYU2H6ZTP3WLK5',
        ),
        SimpleFunctionalMailTextPlaceholder(
            # join vouchers with two spaces at end of line so markdown-parser inserts a <br>
            'voucher_list',
            ['voucher_list'],
            lambda voucher_list: '  \n'.join(voucher_list),
            '    68CYU2H6ZTP3WLK5\n    7MB94KKPVEPSMVF2',
        ),
        SimpleFunctionalMailTextPlaceholder(
            'url',
            ['event', 'voucher_list'],
            lambda event, voucher_list: build_absolute_uri(
                event,
                'presale:event.index',
                kwargs={
                    'event': event.slug,
                    'organizer': event.organizer.slug,
                },
            ),
            lambda event: build_absolute_uri(
                event,
                'presale:event.index',
                kwargs={
                    'event': event.slug,
                    'organizer': event.organizer.slug,
                },
            ),
        ),
        SimpleFunctionalMailTextPlaceholder('name', ['name'], lambda name: name, _('John Doe')),
        SimpleFunctionalMailTextPlaceholder(
            'comment',
            ['comment'],
            lambda comment: comment,
            _('An individual text with a reason can be inserted here.'),
        ),
        SimpleFunctionalMailTextPlaceholder(
            'payment_info',
            ['order', 'payment'],
            _placeholder_payment,
            _('The amount has been charged to your card.'),
        ),
        SimpleFunctionalMailTextPlaceholder(
            'payment_info',
            ['payment_info'],
            lambda payment_info: payment_info,
            _('Please transfer money to this bank account: 9999-9999-9999-9999'),
        ),
        SimpleFunctionalMailTextPlaceholder(
            'attendee_name',
            ['position'],
            lambda position: position.attendee_name,
            _('John Doe'),
        ),
        SimpleFunctionalMailTextPlaceholder(
            'name',
            ['position_or_address'],
            get_best_name,
            _('John Doe'),
        ),
    ]
    if 'pretix_venueless' in sender.get_plugins():
        ph.append(
            SimpleFunctionalMailTextPlaceholder(
                'join_online_event',
                ['order', 'event'],
                lambda order, event: build_join_video_url(event=event, order=order),
                generate_sample_video_url(),
            ),
        )
    name_scheme = PERSON_NAME_SCHEMES[sender.settings.name_scheme]
    for f, l, w in name_scheme['fields']:
        if f == 'full_name':
            continue
        ph.append(
            SimpleFunctionalMailTextPlaceholder(
                'attendee_name_%s' % f,
                ['position'],
                lambda position, f=f: position.attendee_name_parts.get(f, ''),
                name_scheme['sample'][f],
            )
        )
        ph.append(
            SimpleFunctionalMailTextPlaceholder(
                'name_%s' % f,
                ['position_or_address'],
                lambda position_or_address, f=f: get_best_name(position_or_address, parts=True).get(f, ''),
                name_scheme['sample'][f],
            )
        )

    for k, v in sender.meta_data.items():
        ph.append(
            SimpleFunctionalMailTextPlaceholder('meta_%s' % k, ['event'], lambda event, k=k: event.meta_data[k], v)
        )

    return ph

