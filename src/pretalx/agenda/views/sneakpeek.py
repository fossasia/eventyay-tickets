from django.http import HttpResponseRedirect
from django.views.generic import TemplateView
from django_context_decorator import context

from pretalx.common.mixins.views import EventPermissionRequired
from pretalx.submission.models import SubmissionStates


class SneakpeekView(EventPermissionRequired, TemplateView):
    template_name = 'agenda/sneakpeek.html'
    permission_required = 'agenda.view_sneak_peek'

    @context
    def talks(self):
        return self.request.event.submissions.filter(
            state__in=[SubmissionStates.ACCEPTED, SubmissionStates.CONFIRMED],
            is_featured=True,
        ).select_related('event', 'submission_type').prefetch_related('speakers').order_by('title')

    def dispatch(self, request, *args, **kwargs):
        can_peek = self.has_permission()
        can_schedule = request.user.has_perm('agenda.view_schedule', request.event)

        if not can_peek and can_schedule:
            return HttpResponseRedirect(request.event.urls.schedule)
        return super().dispatch(request, *args, **kwargs)
