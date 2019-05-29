import hashlib
import textwrap
from datetime import timedelta
from urllib.parse import unquote

import pytz
from django.http import (
    Http404, HttpResponse, HttpResponseNotModified, HttpResponsePermanentRedirect,
)
from django.urls import resolve, reverse
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _
from django.views.generic import TemplateView
from django_context_decorator import context

from pretalx.common.mixins.views import EventPermissionRequired
from pretalx.common.signals import register_data_exporters


class ScheduleDataView(EventPermissionRequired, TemplateView):
    permission_required = 'agenda.view_schedule'

    @cached_property
    def version(self):
        if 'version' in self.kwargs:
            return unquote(self.kwargs['version'])
        return None

    def dispatch(self, request, *args, **kwargs):
        if 'version' in request.GET:
            kwargs['version'] = request.GET['version']
            return HttpResponsePermanentRedirect(
                reverse(
                    f'agenda:versioned-{request.resolver_match.url_name}',
                    args=args,
                    kwargs=kwargs,
                )
            )
        return super().dispatch(request, *args, **kwargs)

    def get_object(self):
        if self.version:
            return self.request.event.schedules.filter(
                version__iexact=self.version
            ).first()
        if self.request.event.current_schedule:
            return self.request.event.current_schedule
        return None

    @context
    @cached_property
    def schedule(self):
        return self.get_object()

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        schedule = self.schedule
        event = self.request.event

        if not schedule and self.version:
            result['version'] = self.version
            result['error'] = f'Schedule "{self.version}" not found.'
            return result
        if not schedule:
            result['error'] = 'Schedule not found.'
            return result
        result['schedules'] = event.schedules.filter(
            published__isnull=False
        ).values_list('version')
        return result


class ExporterView(ScheduleDataView):
    def get_exporter(self, request):
        url = resolve(request.path_info)

        if url.url_name == 'export':
            exporter = url.kwargs.get('name') or unquote(
                self.request.GET.get('exporter')
            )
        else:
            exporter = url.url_name

        exporter = exporter.lstrip('export.')
        responses = register_data_exporters.send(request.event)
        for sender, response in responses:
            ex = response(request.event)
            if ex.identifier == exporter:
                if ex.public or request.is_orga:
                    return ex
        return None

    def get(self, request, *args, **kwargs):
        exporter = self.get_exporter(request)
        if not exporter:
            raise Http404()
        try:
            exporter.schedule = self.schedule
            exporter.is_orga = getattr(self.request, 'is_orga', False)
            file_name, file_type, data = exporter.render()
            etag = hashlib.sha1(str(data).encode()).hexdigest()
            if 'If-None-Match' in request.headers:
                if request.headers['If-None-Match'] == etag:
                    return HttpResponseNotModified()
            resp = HttpResponse(data, content_type=file_type)
            resp['ETag'] = etag
            if file_type not in ['application/json', 'text/xml']:
                resp['Content-Disposition'] = f'attachment; filename="{file_name}"'
            return resp
        except Exception:
            raise Http404()


class ScheduleView(ScheduleDataView):
    template_name = 'agenda/schedule.html'
    permission_required = 'agenda.view_schedule'

    def _get_text_list(self, data):
        result = ''
        for date in data:
            talk_list = sorted(
                (
                    talk
                    for room in date['rooms']
                    for talk in room.get('talks', [])
                ),
                key=lambda x: x.start
            )
            if talk_list:
                result += '\033[33m{:%Y-%m-%d}\033[0m\n'.format(date['start'])
                result += ''.join(
                    '* \033[33m{:%H:%M}\033[0m {} ({}), {}; in {}\n'.format(
                        talk.start, talk.submission.title,
                        talk.submission.content_locale,
                        talk.submission.display_speaker_names or _('No speakers'),
                        talk.room.name,
                    )
                    for talk in talk_list
                )
        return result

    def _get_text_table(self, data):
        pass

    def get_text(self, request, **kwargs):
        data, max_rooms = self.get_schedule_data()
        response_start = textwrap.dedent(f'''
        \033[1m{request.event.name}\033[0m

        Get different formats:
           curl {request.event.urls.schedule.full()}\?format=table (default)
           curl {request.event.urls.schedule.full()}\?format=list

        ''')
        output_format = request.GET.get('format', 'table')
        if output_format not in ['list', 'table']:
            output_format = 'table'
        if output_format == 'list':
            result = self._get_text_list(data)
        else:
            result = self._get_text_table(data)

        return HttpResponse(
            response_start + result,
            content_type='text/plain',
        )

    def get(self, request, **kwargs):
        if 'text/html' not in request.headers.get('Accept', ''):
            return self.get_text(request, **kwargs)
        return super().get(request, **kwargs)

    def get_object(self):
        if self.version == 'wip' and self.request.user.has_perm(
            'orga.view_schedule', self.request.event
        ):
            return self.request.event.wip_schedule
        return super().get_object()

    @context
    def exporters(self):
        return list(
            exporter(self.request.event)
            for _, exporter in register_data_exporters.send(self.request.event)
        )

    @context
    def search(self):
        return self.request.GET.get('q', '').lower()

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        if 'schedule' not in result:
            return result

        result['data'], result['max_rooms'] = self.get_schedule_data()
        return result

    def get_schedule_data(self):
        from pretalx.schedule.exporters import ScheduleData

        timezone = pytz.timezone(self.request.event.timezone)
        data = ScheduleData(
            event=self.request.event, schedule=self.schedule
        ).data
        max_rooms = 0
        for date in data:
            if date.get('first_start') and date.get('last_end'):
                start = (
                    date.get('first_start')
                    .astimezone(timezone)
                    .replace(second=0, minute=0)
                )
                end = date.get('last_end').astimezone(timezone)
                date['height'] = int((end - start).total_seconds() / 60 * 2)
                date['hours'] = []
                step = start
                while step < end:
                    date['hours'].append(step.strftime('%H:%M'))
                    step += timedelta(hours=1)
                max_rooms = max(max_rooms, len(date['rooms']))
                for room in date['rooms']:
                    for talk in room.get('talks', []):
                        talk.top = int(
                            (talk.start.astimezone(timezone) - start).total_seconds()
                            / 60
                            * 2
                        )
                        talk.height = int(talk.duration * 2)
                        talk.is_active = talk.start <= now() <= talk.real_end
        return data, max_rooms


class ChangelogView(EventPermissionRequired, TemplateView):
    template_name = 'agenda/changelog.html'
    permission_required = 'agenda.view_schedule'
