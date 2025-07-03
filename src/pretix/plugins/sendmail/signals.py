from django.dispatch import receiver
from django.urls import resolve, reverse
from django.utils.translation import gettext_lazy as _

from pretix.base.signals import logentry_display
from pretix.control.signals import nav_event


@receiver(nav_event, dispatch_uid='sendmail_nav')
def control_nav_import(sender, request=None, **kwargs):
    url = resolve(request.path_info)
    if not request.user.has_event_permission(request.organizer, request.event, 'can_change_orders', request=request):
        return []
    return [
        {
            'label': _('Mails'),
            'url': reverse(
                'plugins:sendmail:outbox',
                kwargs={
                    'event': request.event.slug,
                    'organizer': request.event.organizer.slug,
                },
            ),
            'active': (url.namespace == 'plugins:sendmail' and url.url_name == 'send'),
            'icon': 'envelope',
            'children': [
                {
                    'label': _('Outbox'),
                    'url': reverse(
                        'plugins:sendmail:outbox',
                        kwargs={
                            'event': request.event.slug,
                            'organizer': request.event.organizer.slug,
                        },
                    ),
                    'active': (url.namespace == 'plugins:sendmail' and url.url_name == 'outbox'),
                },
                {
                    'label': _('Compose emails'),
                    'url': reverse(
                        'plugins:sendmail:compose_email_choice',
                        kwargs={
                            'event': request.event.slug,
                            'organizer': request.event.organizer.slug,
                        },
                    ),
                    'active': (url.namespace == 'plugins:compose' and url.url_name == 'compose_email_choice'),
                },
                {
                    'label': _('Sent emails'),
                    'url': reverse(
                        'plugins:sendmail:history',
                        kwargs={
                            'event': request.event.slug,
                            'organizer': request.event.organizer.slug,
                        },
                    ),
                    'active': (url.namespace == 'plugins:sendmail' and url.url_name == 'history'),
                },
                {
                    'label': _('Sent emails'),
                    'url': reverse(
                        'plugins:sendmail:sent',
                        kwargs={
                            'event': request.event.slug,
                            'organizer': request.event.organizer.slug,
                        },
                    ),
                    'active': (url.namespace == 'plugins:sendmail' and url.url_name == 'sent'),
                },
                {
                    'label': _('Templates'),
                    'url': reverse(
                        'plugins:sendmail:templates',
                        kwargs={
                            'event': request.event.slug,
                            'organizer': request.event.organizer.slug,
                        },
                    ),
                    'active': (url.namespace == 'plugins:sendmail' and url.url_name == 'templates'),
                },
            ],
        },
    ]


@receiver(signal=logentry_display)
def pretixcontrol_logentry_display(sender, logentry, **kwargs):
    plains = {
        'pretix.plugins.sendmail.sent': _('Email was sent'),
        'pretix.plugins.sendmail.order.email.sent': _('The order received a mass email.'),
        'pretix.plugins.sendmail.order.email.sent.attendee': _('A ticket holder of this order received a mass email.'),
    }
    if logentry.action_type in plains:
        return plains[logentry.action_type]
