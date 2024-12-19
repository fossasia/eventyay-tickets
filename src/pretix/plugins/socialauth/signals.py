from django.dispatch import receiver
from django.urls import resolve, reverse
from django.utils.translation import gettext_lazy as _

from pretix.control.signals import nav_global


@receiver(nav_global, dispatch_uid='social_uid')
def navbar_global(sender, request, **kwargs):
    url = resolve(request.path_info)
    return [
        {
            'parent': reverse('control:admin.global.settings'),
            'label': _('Social login settings'),
            'url': reverse('plugins:socialauth:admin.global.social.auth.settings'),
            'active': (url.url_name == 'admin.global.social.auth.settings')
        }
    ]
