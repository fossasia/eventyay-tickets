from bakery.views import BuildableDetailView
from django.utils import translation

from pretalx.agenda.views.schedule import ScheduleView
from pretalx.agenda.views.speaker import SpeakerView
from pretalx.agenda.views.talk import TalkView
from pretalx.event.models import Event
from pretalx.person.models import SpeakerProfile
from pretalx.schedule.models import Schedule
from pretalx.submission.models import Submission

# TODO: use the default langauge for each event
translation.activate('en-gb')


class PretalxExportContextMixin():
    def build_object(self, obj):
        self._object = obj
        super().build_object(obj)

    def create_request(self, *args, **kwargs):
        request = super().create_request(*args, **kwargs)
        request.event = self._object.event  # django-bakery/RequestFactory does not support middlewares
        return request

    def get_context_data(self, *args, **kwargs):
        self.object = self.get_object()  # ScheduleView crashes without this

        ctx = super().get_context_data(*args, **kwargs)
        ctx['is_html_export'] = True
        return ctx

    def get_url(self, obj):
        return obj.urls.public

    def get_queryset(self):
        qs = super().get_queryset()
        # TODO: make exported event configurable somehow
        qs = qs.filter(event=Event.objects.all().first())
        return qs


# current schedule
class ExportScheduleView(PretalxExportContextMixin, BuildableDetailView, ScheduleView):
    queryset = Schedule.objects.filter(published__isnull=False).order_by('published')

    def get_url(self, obj):
        return obj.event.urls.schedule


# all schedule versions
class ExportScheduleVersionsView(PretalxExportContextMixin, BuildableDetailView, ScheduleView):
    queryset = Schedule.objects.filter(version__isnull=False)


class ExportTalkView(PretalxExportContextMixin, BuildableDetailView, TalkView):
    queryset = Submission.objects.filter(slots__schedule__published__isnull=False).distinct()


class ExportSpeakerView(PretalxExportContextMixin, BuildableDetailView, SpeakerView):
    queryset = SpeakerProfile.objects.filter(user__submissions__slots__schedule__published__isnull=False).distinct()
