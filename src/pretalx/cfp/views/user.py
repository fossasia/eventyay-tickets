from django.views.generic import ListView

from pretalx.cfp.views.event import LoggedInEventPageMixin


class SubmissionsListView(LoggedInEventPageMixin, ListView):
    template_name = 'cfp/event/user_submissions.html'
    context_object_name = 'submissions'

    def get_queryset(self):
        return self.request.event.submissions.filter(speakers__in=[self.request.user])
