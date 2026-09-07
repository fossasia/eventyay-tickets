from django.dispatch import receiver
from django.urls import resolve, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from eventyay.base.signals import logentry_display
from eventyay.control.signals import nav_event
from eventyay.plugins.sendmail.models import EmailQueue


@receiver(nav_event, dispatch_uid='sendmail_nav')
def control_nav_import(sender, request=None, **kwargs):
    url = resolve(request.path_info)
    if not request.user.has_event_permission(request.organizer, request.event, 'can_change_orders', request=request):
        return []
    pending_mails = EmailQueue.objects.filter(
        event=request.event,
        sent_at__isnull=True,
        is_draft=False,
    ).count()

    return [
        {
            'label': format_html(
                '{} <span class="badge badge-warning">{}</span>',
                _('Message center'),
                pending_mails,
            ) if pending_mails > 0 else _('Message center'),
            'url': reverse(
                'control:event.mail.outbox',
                kwargs={
                    'event': request.event.slug,
                    'organizer': request.event.organizer.slug,
                },
            ),
            'active': (url.url_name == 'event.mail.outbox'),
            'icon': 'envelope',
            'children': [
                {
                    'label': _('Outbox'),
                    'url': reverse(
                        'control:event.mail.outbox',
                        kwargs={
                            'event': request.event.slug,
                            'organizer': request.event.organizer.slug,
                        },
                    ),
                    'active': (
                        url.url_name in {
                            'event.mail.outbox',
                            'event.mail.edit',
                            'event.mail.outbox.delete',
                            'event.mail.outbox.purge'
                        }
                    ),
                },
                {
                    'label': _('Compose'),
                    'url': reverse(
                        'control:event.mail.compose',
                        kwargs={
                            'event': request.event.slug,
                            'organizer': request.event.organizer.slug,
                        },
                    ),
                    'active': (
                        url.url_name in {
                            'event.mail.compose',
                            'event.mail.compose_teams',
                            'event.mail.send'
                        }
                    ),
                },
                {
                    'label': _('Drafts'),
                    'url': reverse(
                        'control:event.mail.drafts',
                        kwargs={
                            'event': request.event.slug,
                            'organizer': request.event.organizer.slug,
                        },
                    ),
                    'active': (url.url_name == 'event.mail.drafts'),
                },
                {
                    'label': _('Sent'),
                    'url': reverse(
                        'control:event.mail.sent',
                        kwargs={
                            'event': request.event.slug,
                            'organizer': request.event.organizer.slug,
                        },
                    ),
                    'active': (url.url_name == 'event.mail.sent'),
                },
                {
                    'label': _('Templates'),
                    'url': reverse(
                        'control:event.mail.templates',
                        kwargs={
                            'event': request.event.slug,
                            'organizer': request.event.organizer.slug,
                        },
                    ),
                    'active': (url.url_name == 'event.mail.templates'),
                },
            ],
        },
    ]


@receiver(signal=logentry_display)
def pretixcontrol_logentry_display(sender, logentry, **kwargs):
    plains = {
        'eventyay.plugins.sendmail.sent': _('Email was sent'),
        'eventyay.plugins.sendmail.order.email.sent': _('The order received a mass email.'),
        'eventyay.plugins.sendmail.order.email.sent.attendee': _('A ticket holder of this order received a mass email.'),
    }
    if logentry.action_type in plains:
        return plains[logentry.action_type]
