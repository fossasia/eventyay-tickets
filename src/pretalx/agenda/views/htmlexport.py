import os

from bakery.views import BuildableDetailView
from django.conf import settings

from pretalx.agenda.views.schedule import ExporterView, ScheduleView
from pretalx.agenda.views.speaker import SpeakerView
from pretalx.agenda.views.talk import SingleICalView, TalkView
from pretalx.person.models import SpeakerProfile
from pretalx.schedule.models import Schedule
from pretalx.submission.models import Submission


class PretalxExportContextMixin():
    def __init__(self, *args, **kwargs):
        self._exporting_event = kwargs.pop('_exporting_event', None)

        if not self._exporting_event:
            raise Exception('Use the provided "export_schedule_html" management command to export the HTML schedule.')

        super().__init__(*args, **kwargs)

    def create_request(self, *args, **kwargs):
        request = super().create_request(*args, **kwargs)
        request.event = self._exporting_event
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
        return qs.filter(event=self._exporting_event)

    def get_file_build_path(self, obj):
        dir_path, file_name = os.path.split(self.get_url(obj))

        path = os.path.join(settings.BUILD_DIR, dir_path[1:])
        os.path.exists(path) or os.makedirs(path)

        return os.path.join(path, file_name)


# current schedule
class ExportScheduleView(PretalxExportContextMixin, BuildableDetailView, ScheduleView):
    queryset = Schedule.objects.filter(published__isnull=False).order_by('published')

    def get_url(self, obj):
        return obj.event.urls.schedule


class ExportFrabXmlView(PretalxExportContextMixin, BuildableDetailView, ExporterView):
    queryset = Schedule.objects.filter(published__isnull=False).order_by('published')

    def get_url(self, obj):
        return obj.event.urls.frab_xml

    def get_content(self):
        return self.get(self.request, self._exporting_event).content

    def get_build_path(self, obj):
        return self.get_file_build_path(obj)


class ExportFrabXCalView(PretalxExportContextMixin, BuildableDetailView, ExporterView):
    queryset = Schedule.objects.filter(published__isnull=False).order_by('published')

    def get_url(self, obj):
        return obj.event.urls.frab_xcal

    def get_content(self):
        return self.get(self.request, self._exporting_event).content

    def get_build_path(self, obj):
        return self.get_file_build_path(obj)


class ExportFrabJsonView(PretalxExportContextMixin, BuildableDetailView, ExporterView):
    queryset = Schedule.objects.filter(published__isnull=False).order_by('published')

    def get_url(self, obj):
        return obj.event.urls.frab_json

    def get_content(self):
        return self.get(self.request, self._exporting_event).content

    def get_build_path(self, obj):
        return self.get_file_build_path(obj)


class ExportICalView(PretalxExportContextMixin, BuildableDetailView, ExporterView):
    queryset = Schedule.objects.filter(published__isnull=False).order_by('published')

    def get_url(self, obj):
        return obj.event.urls.ical

    def get_content(self):
        return self.get(self.request, self._exporting_event).content

    def get_build_path(self, obj):
        return self.get_file_build_path(obj)


# all schedule versions
class ExportScheduleVersionsView(PretalxExportContextMixin, BuildableDetailView, ScheduleView):
    queryset = Schedule.objects.filter(version__isnull=False)


class ExportTalkView(PretalxExportContextMixin, BuildableDetailView, TalkView):
    queryset = Submission.objects.filter(slots__schedule__published__isnull=False).distinct()


class ExportTalkICalView(PretalxExportContextMixin, BuildableDetailView, SingleICalView):
    queryset = Submission.objects.filter(slots__schedule__published__isnull=False).distinct()

    def get_url(self, obj):
        return obj.urls.ical

    def get_content(self):
        return self.get(self.request, self._exporting_event).content

    def get_build_path(self, obj):
        return self.get_file_build_path(obj)


class ExportSpeakerView(PretalxExportContextMixin, BuildableDetailView, SpeakerView):
    queryset = SpeakerProfile.objects.filter(user__submissions__slots__schedule__published__isnull=False).distinct()
