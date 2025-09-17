import logging
from django.dispatch import receiver
from django.template.loader import get_template
from django.urls import resolve, reverse
from django.utils.translation import gettext_lazy as _

from eventyay.control.signals import html_head, nav_event

logger = logging.getLogger(__name__)


@receiver(nav_event, dispatch_uid='exhibitor_nav')
def control_nav_exhibitor(sender, request=None, **kwargs):
    """Add exhibitor management to the event navigation menu."""
    if not request or not hasattr(request, 'event'):
        return []
    
    # Check permissions
    if not request.user.has_event_permission(
        request.organizer, 
        request.event, 
        'can_change_event_settings', 
        request=request
    ):
        return []
    
    url = resolve(request.path_info)
    
    return [
        {
            'label': _('Exhibitors'),
            'url': reverse(
                'plugins:exhibitor:index',
                kwargs={
                    'event': request.event.slug,
                    'organizer': request.event.organizer.slug,
                },
            ),
            'icon': 'building',
            'children': [
                {
                    'label': _('Exhibitor List'),
                    'url': reverse(
                        'plugins:exhibitor:list',
                        kwargs={
                            'event': request.event.slug,
                            'organizer': request.event.organizer.slug,
                        },
                    ),
                    'active': (
                        url.namespace == 'plugins:exhibitor' and 
                        url.url_name in ['list', 'detail', 'create', 'edit']
                    ),
                },
                {
                    'label': _('Lead Management'),
                    'url': reverse(
                        'plugins:exhibitor:leads',
                        kwargs={
                            'event': request.event.slug,
                            'organizer': request.event.organizer.slug,
                        },
                    ),
                    'active': (
                        url.namespace == 'plugins:exhibitor' and 
                        url.url_name.startswith('leads')
                    ),
                },
                {
                    'label': _('Settings'),
                    'url': reverse(
                        'plugins:exhibitor:settings',
                        kwargs={
                            'event': request.event.slug,
                            'organizer': request.event.organizer.slug,
                        },
                    ),
                    'active': (
                        url.namespace == 'plugins:exhibitor' and 
                        url.url_name == 'settings'
                    ),
                },
            ],
        },
    ]


@receiver(html_head, dispatch_uid='exhibitor_html_head')
def html_head_exhibitor(sender, request=None, **kwargs):
    """Add exhibitor-specific CSS and JavaScript to the HTML head."""
    if not request:
        return ''
    
    url = resolve(request.path_info)
    if url.namespace == 'plugins:exhibitor':
        try:
            template = get_template('exhibitor/control_head.html')
            return template.render({'request': request})
        except Exception as e:
            logger.warning(f"Could not render exhibitor control head template: {e}")
            return ''
    
    return ''