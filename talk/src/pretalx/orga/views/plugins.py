from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect
from django.utils.functional import cached_property
from django.views.generic import TemplateView
from django_context_decorator import context

from pretalx.common.plugins import get_all_plugins_grouped
from pretalx.common.text.phrases import phrases
from pretalx.common.views.mixins import EventPermissionRequired


class EventPluginsView(EventPermissionRequired, TemplateView):
    template_name = "orga/plugins.html"
    permission_required = "event.update_event"

    @context
    @cached_property
    def grouped_plugins(self):
        return get_all_plugins_grouped(self.request.event)

    @context
    def tablist(self):
        return {key: value for key, value in self.grouped_plugins.keys()}

    @context
    @cached_property
    def plugins_active(self):
        return self.request.event.plugin_list

    def post(self, request, *args, **kwargs):
        with transaction.atomic():
            for key, value in request.POST.items():
                if key.startswith("plugin:"):
                    module = key.split(":", maxsplit=1)[1]
                    if (
                        value == "enable"
                        and module in self.request.event.available_plugins
                    ):
                        self.request.event.enable_plugin(module)
                        self.request.event.log_action(
                            "pretalx.event.plugins.enabled",
                            person=self.request.user,
                            data={"plugin": module},
                            orga=True,
                        )
                    else:
                        self.request.event.disable_plugin(module)
                        self.request.event.log_action(
                            "pretalx.event.plugins.disabled",
                            person=self.request.user,
                            data={"plugin": module},
                            orga=True,
                        )
            self.request.event.save()
            messages.success(self.request, phrases.base.saved)
        return redirect(self.request.event.orga_urls.plugins)
