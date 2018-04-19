from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect
from django.utils.translation import ugettext_lazy as _
from django.views.generic import TemplateView

from pretalx.common.mixins.views import PermissionRequired


class EventPluginsView(PermissionRequired, TemplateView):
    template_name = 'orga/plugins.html'
    permission_required = 'orga.change_plugins'

    def get_object(self):
        return self.request.event

    def get_context_data(self, *args, **kwargs) -> dict:
        from pretalx.common.plugins import get_all_plugins
        context = super().get_context_data(*args, **kwargs)
        context['plugins'] = [p for p in get_all_plugins() if not p.name.startswith('.')]
        context['plugins_active'] = self.request.event.get_plugins()
        return context

    def post(self, request, *args, **kwargs):
        from pretalx.common.plugins import get_all_plugins

        plugins_active = self.request.event.get_plugins()
        plugins_available = {
            p.module: p for p in get_all_plugins()
            if not p.name.startswith('.') and getattr(p, 'visible', True)
        }

        with transaction.atomic():
            for key, value in request.POST.items():
                if key.startswith("plugin:"):
                    module = key.split(":", maxsplit=1)[1]
                    if value == "enable" and module in plugins_available:
                        if hasattr(plugins_available[module].app, 'installed'):
                            getattr(plugins_available[module].app, 'installed')(self.request.event)

                        self.request.event.log_action('pretalx.event.plugins.enabled', person=self.request.user, data={'plugin': module}, orga=True)
                        if module not in plugins_active:
                            plugins_active.append(module)
                    else:
                        self.request.event.log_action('pretalx.event.plugins.disabled', person=self.request.user, data={'plugin': module}, orga=True)
                        if module in plugins_active:
                            plugins_active.remove(module)
            self.request.event.plugins = ','.join(plugins_active)
            self.request.event.save()
            messages.success(self.request, _('Your changes have been saved.'))
        return redirect(self.request.event.orga_urls.plugins)
