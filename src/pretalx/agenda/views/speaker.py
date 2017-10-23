from django.views.generic import DetailView

from pretalx.person.models import SpeakerProfile, User
from pretalx.submission.models import SubmissionStates


class SpeakerView(DetailView):
    template_name = 'agenda/speaker.html'
    context_object_name = 'speaker'

    def get_object(self):
        user = User.objects.get(code=self.kwargs['code'])
        if not user.submissions.filter(event=self.request.event, state=SubmissionStates.CONFIRMED).exists():
            return None
        return user

    def get_context_data(self, object):
        context = super().get_context_data()
        context['profile'] = SpeakerProfile.objects.get(user=object, event=self.request.event)
        context['talks'] = object.submissions.filter(event=self.request.event, state=SubmissionStates.CONFIRMED)
        return context
