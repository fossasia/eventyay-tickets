from django.http import HttpResponseRedirect
from django.views.generic import TemplateView

from pretalx.common.mixins.views import PermissionRequired


class SneakpeekView(PermissionRequired, TemplateView):
    template_name = 'agenda/sneakpeek.html'
    permission_required = 'agenda.view_sneak_peek'

    def get_permission_object(self):
        return self.request.event

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['talks'] = self.request.event.submissions.filter(is_featured=True).order_by('id')
        return ctx

    def dispatch(self, *args, **kwargs):
        can_peek = self.has_permission()
        can_schedule = self.request.user.has_perm('agenda.view_schedule', self.request.event)

        if not can_peek and can_schedule:
            return HttpResponseRedirect(self.request.event.urls.schedule)
        else:
            return super().dispatch(*args, **kwargs)
