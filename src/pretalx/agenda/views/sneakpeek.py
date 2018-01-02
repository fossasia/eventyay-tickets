from django.views.generic import TemplateView

from pretalx.common.mixins.views import PermissionRequired


class SneakpeekView(PermissionRequired, TemplateView):
    template_name = 'agenda/sneakpeek.html'
    permission_required = 'agenda.view_schedule'  # TODO: this is suppoed to be a _preview_, d'uh!

    def get_permission_object(self):
        return self.request.event

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['talks'] = self.request.event.submissions.filter(
            state=SubmissionStates.CONFIRMED,
        ).order_by('id')[:15]
        return ctx
