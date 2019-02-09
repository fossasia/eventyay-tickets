from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect
from django.utils.translation import ugettext_lazy as _
from django.views.generic import TemplateView

from pretalx.common.mixins.views import EventPermissionRequired


class EventPluginsView(EventPermissionRequired, TemplateView):
    template_name = 'orga/plugins.html'
    permission_required = 'orga.change_plugins'

    def get_context_data(self, **kwargs) -> dict:
        from pretalx.common.plugins import get_all_plugins

        context = super().get_context_data(**kwargs)
        context['plugins'] = [
            p for p in get_all_plugins(self.request.event)
            if not p.name.startswith('.') and getattr(p, 'visible', True)
        ]
        context['plugins_active'] = self.request.event.get_plugins()
        return context

    def post(self, request, *args, **kwargs):
        from pretalx.common.plugins import get_all_plugins
        plugins_available = {
            p.module for p in get_all_plugins(self.request.event)
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
