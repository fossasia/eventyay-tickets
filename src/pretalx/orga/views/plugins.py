from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect
from django.utils.translation import ugettext_lazy as _
from django.views.generic import TemplateView
from django_context_decorator import context

from pretalx.common.mixins.views import EventPermissionRequired
from pretalx.common.plugins import get_all_plugins


class EventPluginsView(EventPermissionRequired, TemplateView):
    template_name = 'orga/plugins.html'
    permission_required = 'orga.change_plugins'

    @context
    def plugins(self):
        return [
            p
            for p in get_all_plugins(self.request.event)
            if not p.name.startswith('.') and getattr(p, 'visible', True)
        ]

    @context
    def plugins_active(self):
        return self.request.event.plugin_list

    def post(self, request, *args, **kwargs):
        plugins_available = {
            p.module
            for p in get_all_plugins(self.request.event)
            if not p.name.startswith('.') and getattr(p, 'visible', True)
        }

        with transaction.atomic():
            for key, value in request.POST.items():
                if key.startswith("plugin:"):
                    module = key.split(":", maxsplit=1)[1]
                    if value == "enable" and module in plugins_available:
                        self.request.event.enable_plugin(module)
                        self.request.event.log_action(
                            'pretalx.event.plugins.enabled',
                            person=self.request.user,
                            data={'plugin': module},
                            orga=True,
                        )
                    else:
                        self.request.event.disable_plugin(module)
                        self.request.event.log_action(
                            'pretalx.event.plugins.disabled',
                            person=self.request.user,
                            data={'plugin': module},
                            orga=True,
                        )
            self.request.event.save()
            messages.success(self.request, _('Your changes have been saved.'))
        return redirect(self.request.event.orga_urls.plugins)
