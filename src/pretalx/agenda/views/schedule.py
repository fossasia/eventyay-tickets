from datetime import timedelta
from urllib.parse import unquote

import pytz
from csp.decorators import csp_update
from django.http import Http404, HttpResponse, HttpResponsePermanentRedirect
from django.urls import resolve, reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.views.generic import TemplateView

from pretalx.common.mixins.views import PermissionRequired
from pretalx.common.signals import register_data_exporters


class ScheduleDataView(PermissionRequired, TemplateView):
    template_name = 'agenda/schedule.html'
    permission_required = 'agenda.view_schedule'

    def get_permission_object(self):
        return self.request.event

    @cached_property
    def version(self):
        if 'version' in self.kwargs:
            return unquote(self.kwargs['version'])
        else:
            return None

    def dispatch(self, request, *args, **kwargs):
        if 'version' in request.GET:
            if request.resolver_match.url_name.startswith('versioned-'):
                raise Exception('The schedule version can be supplied in the path or querystring, but not both.')

            kwargs['version'] = request.GET['version']
            return HttpResponsePermanentRedirect(reverse(
                f'agenda:versioned-{request.resolver_match.url_name}',
                args=args, kwargs=kwargs
            ))
        else:
            return super().dispatch(request, *args, **kwargs)

    def get_object(self):
        if self.version:
            return self.request.event.schedules.filter(version=self.version).first()
        if self.request.event.current_schedule:
            return self.request.event.current_schedule

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        schedule = self.get_object()
        event = self.request.event

        if not schedule and self.version:
            ctx['version'] = self.version
            ctx['error'] = f'Schedule "{self.version}" not found.'
            return ctx
        elif not schedule:
            ctx['error'] = 'Schedule not found.'
            return ctx
        ctx['schedule'] = schedule
        ctx['schedules'] = event.schedules.filter(published__isnull=False).values_list('version')
        return ctx


class ExporterView(ScheduleDataView):
    permission_required = 'agenda.view_schedule'

    def get_permission_object(self):
        return self.request.event

    def get_exporter(self, request):
        from pretalx.common.signals import register_data_exporters

        url = resolve(request.path_info)
        if url.url_name == 'export':
            exporter = unquote(self.request.GET.get('exporter'))
        else:
            exporter = url.url_name

        responses = register_data_exporters.send(request.event)
        for receiver, response in responses:
            ex = response(request.event)
            if ex.identifier == exporter:
                if ex.public or request.is_orga:
                    return ex

    def get(self, request, *args, **kwargs):
        exporter = self.get_exporter(request)
        if not exporter:
            raise Http404()
        exporter.schedule = self.get_object()
        exporter.is_orga = getattr(self.request, 'is_orga', False)
        file_name, file_type, data = exporter.render()
        resp = HttpResponse(data, content_type=file_type)
        if file_type not in ['application/json', 'text/xml']:
            resp['Content-Disposition'] = f'attachment; filename="{file_name}"'
        return resp


@method_decorator(csp_update(STYLE_SRC="'self' 'unsafe-inline'"), name='dispatch')
class ScheduleView(ScheduleDataView):
    template_name = 'agenda/schedule.html'
    permission_required = 'agenda.view_schedule'

    def get_permission_object(self):
        return self.request.event

    def get_object(self):
        if self.version == 'wip' and self.request.user.has_perm('orga.view_schedule', self.request.event):
            return self.request.event.wip_schedule
        return super().get_object()

    def get_context_data(self, *args, **kwargs):
        from pretalx.schedule.exporters import ScheduleData
        ctx = super().get_context_data(*args, **kwargs)
        ctx['exporters'] = list(exporter(self.request.event) for _, exporter in register_data_exporters.send(self.request.event))
        tz = pytz.timezone(self.request.event.timezone)
        if 'schedule' not in ctx:
            return ctx

        ctx['data'] = ScheduleData(event=self.request.event, schedule=ctx['schedule']).data
        for date in ctx['data']:
            if date.get('first_start') and date.get('last_end'):
                start = date.get('first_start').astimezone(tz).replace(second=0, minute=0)
                end = date.get('last_end').astimezone(tz)
                date['height'] = int((end - start).total_seconds() / 60 * 2)
                date['hours'] = []
                d = start
                while d < end:
                    date['hours'].append(d.strftime('%H:%M'))
                    d += timedelta(hours=1)
                for room in date['rooms']:
                    for talk in room.get('talks', []):
                        talk.top = int((talk.start.astimezone(tz) - start).total_seconds() / 60 * 2)
                        talk.height = int(talk.duration * 2)
                        talk.is_active = talk.start <= now() <= talk.end
        return ctx


class ChangelogView(PermissionRequired, TemplateView):
    template_name = 'agenda/changelog.html'
    permission_required = 'agenda.view_schedule'

    def get_permission_object(self):
        return self.request.event
