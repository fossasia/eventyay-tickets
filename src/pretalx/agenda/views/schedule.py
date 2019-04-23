import hashlib
from datetime import timedelta
from urllib.parse import unquote

import pytz
from django.http import (
    Http404, HttpResponse, HttpResponseNotModified, HttpResponsePermanentRedirect,
)
from django.urls import resolve, reverse
from django.utils.functional import cached_property
from django.utils.timezone import now
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
        for _, response in responses:
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
            if 'HTTP_IF_NONE_MATCH' in request.META:
                if request.META['HTTP_IF_NONE_MATCH'] == etag:
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

    def get_object(self):
        if self.version == 'wip' and self.request.user.has_perm(
            'orga.view_schedule', self.request.event
        ):
            return self.request.event.wip_schedule
        return super().get_object()

    def get_context_data(self, **kwargs):
        from pretalx.schedule.exporters import ScheduleData

        result = super().get_context_data(**kwargs)
        result['exporters'] = list(
            exporter(self.request.event)
            for _, exporter in register_data_exporters.send(self.request.event)
        )
        timezone = pytz.timezone(self.request.event.timezone)
        if 'schedule' not in result:
            return result

        result['data'] = ScheduleData(
            event=self.request.event, schedule=self.schedule
        ).data
        result['search'] = self.request.GET.get('q', '').lower()
        max_rooms = 0
        for date in result['data']:
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
        result['max_rooms'] = max_rooms
        return result


class ChangelogView(EventPermissionRequired, TemplateView):
    template_name = 'agenda/changelog.html'
    permission_required = 'agenda.view_schedule'
