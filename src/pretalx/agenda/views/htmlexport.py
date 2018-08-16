import os

from bakery.views import BuildableDetailView
from django.conf import settings
from django.utils.functional import cached_property

from pretalx.agenda.views.schedule import ExporterView, ScheduleView
from pretalx.agenda.views.speaker import SpeakerView
from pretalx.agenda.views.talk import SingleICalView, TalkView
from pretalx.person.models import SpeakerProfile
from pretalx.schedule.models import Schedule


class PretalxExportContextMixin:
    def __init__(self, *args, _exporting_event=None, **kwargs):
        self._exporting_event = _exporting_event
        super().__init__(*args, **kwargs)

    def create_request(self, *args, **kwargs):
        request = super().create_request(*args, **kwargs)
        request.event = self._exporting_event
        return request

    @cached_property
    def object(self):
        return self.get_object()

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['is_html_export'] = True
        return context

    @staticmethod
    def get_url(obj):
        return obj.urls.public

    def get_queryset(self):
        return super().get_queryset().filter(event=self._exporting_event)

    def get_file_build_path(self, obj):
        dir_path, file_name = os.path.split(self.get_url(obj))
        path = os.path.join(settings.BUILD_DIR, dir_path[1:])
        if not os.path.exists(path):
            os.makedirs(path)
        return os.path.join(path, file_name)


class ExportScheduleView(PretalxExportContextMixin, BuildableDetailView, ScheduleView):
    """ Build the current schedule. """

    queryset = Schedule.objects.filter(published__isnull=False).order_by('published')

    @staticmethod
    def get_url(obj):
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
class ExportScheduleVersionsView(
    PretalxExportContextMixin, BuildableDetailView, ScheduleView
):
    queryset = Schedule.objects.filter(version__isnull=False)


class ExportTalkView(PretalxExportContextMixin, BuildableDetailView, TalkView):
    def get_queryset(self):
        return self._exporting_event.submissions.filter(
            pk__in=self._exporting_event.current_schedule.slots.all().values_list(
                'pk', flat=True
            )
        )


class ExportTalkICalView(
    PretalxExportContextMixin, BuildableDetailView, SingleICalView
):
    def get_queryset(self):
        return self._exporting_event.submissions.filter(
            pk__in=self._exporting_event.current_schedule.slots.all().values_list(
                'pk', flat=True
            )
        )

    @staticmethod
    def get_url(obj):
        return obj.urls.ical

    def get_content(self):
        return self.get(self.request, self._exporting_event).content

    def get_build_path(self, obj):
        return self.get_file_build_path(obj)


class ExportSpeakerView(PretalxExportContextMixin, BuildableDetailView, SpeakerView):
    queryset = SpeakerProfile.objects.filter(
        user__submissions__slots__schedule__published__isnull=False
    ).distinct()
