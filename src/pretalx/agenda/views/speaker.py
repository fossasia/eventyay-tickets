from csp.decorators import csp_update
from django.utils.decorators import method_decorator
from django.views.generic import DetailView

from pretalx.common.mixins.views import PermissionRequired
from pretalx.person.models import SpeakerProfile
from pretalx.submission.models import SubmissionStates


@method_decorator(csp_update(IMG_SRC="https://www.gravatar.com"), name='dispatch')
class SpeakerView(PermissionRequired, DetailView):
    template_name = 'agenda/speaker.html'
    context_object_name = 'profile'
    permission_required = 'agenda.view_speaker'
    slug_field = 'code'

    def get_object(self):
        return SpeakerProfile.objects.filter(
            event=self.request.event, user__code__iexact=self.kwargs['code'],
        ).first()

    def get_context_data(self, object):
        context = super().get_context_data()
        context['speaker'] = object.user
        context['talks'] = object.user.submissions.filter(
            event=self.request.event,
            state=SubmissionStates.CONFIRMED,
            slots__schedule=object.event.current_schedule,
        )
        return context
