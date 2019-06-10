import hashlib
import textwrap
from datetime import timedelta
from urllib.parse import unquote

import pytz
from dateutil import rrule
from django.http import (
    Http404, HttpResponse, HttpResponseNotModified, HttpResponsePermanentRedirect,
)
from django.urls import resolve, reverse
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _
from django.views.generic import TemplateView
from django_context_decorator import context

from pretalx.common.console import LR, UD, get_seperator
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
                result += '\n\033[33m{:%Y-%m-%d}\033[0m\n'.format(date['start'])
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

    def _get_text_table(self, data, col_width=20):
        result = ''
        for date in data:
            result += '\n\033[33m{:%Y-%m-%d}\033[0m\n'.format(date['start'])
            table = self._get_table_for_date(date, col_width=col_width)
            if table:
                result += table
            else:
                result += 'No talks on this day.\n'
        return result

    def _get_table_for_date(self, date, col_width=20):
        talk_list = sorted(
            (
                talk
                for room in date['rooms']
                for talk in room.get('talks', [])
            ),
            key=lambda x: x.start
        )
        if not talk_list:
            return

        global_start = date.get('first_start', min(talk.start for talk in talk_list))
        global_end = date.get('last_end', max(talk.end for talk in talk_list))
        talks_by_room = {str(r['name']): r['talks'] for r in date['rooms']}
        cards_by_id = {talk.pk: self._card(talk, col_width) for talk in talk_list}
        rooms = list(talks_by_room.keys())
        lines = ['        | ' + ' | '.join(f'{room:<{col_width-2}}' for room in rooms)]
        tick_times = rrule.rrule(
            rrule.HOURLY,
            byminute=(0, 30),
            dtstart=global_start,
            until=global_end,
        )

        for dt in rrule.rrule(rrule.HOURLY, byminute=range(0, 60, 5), dtstart=global_start, until=global_end):
            starting_events = {room: next((e for e in talks_by_room[room] if e.start == dt), None) for room in rooms}
            running_events = {room: next((e for e in talks_by_room[room] if e.start < dt < e.real_end), None) for room in rooms}
            ending_events = {room: next((e for e in talks_by_room[room] if e.real_end == dt), None) for room in rooms}
            lines.append(self._get_dt_line(
                dt, dt in tick_times, starting_events, running_events,
                ending_events, rooms, col_width, cards_by_id,
            ))
        return '\n'.join(lines)

    def _get_dt_line(self, dt, is_tick, starting_events, running_events, ending_events, rooms, col_width, cards_by_id):
        line_parts = [f'{dt:%H:%M} --' if is_tick else ' ' * 8]
        fill_char = '-' if is_tick else ' '

        room = rooms[0]
        start, run, end = starting_events[room], running_events[room], ending_events[room]

        if start or end:
            line_parts.append(get_seperator(bool(end), bool(start), False, False) + LR * col_width)
        elif run:
            line_parts.append(UD + next(cards_by_id[run.pk]))
        else:
            line_parts.append(fill_char * (col_width + 1))

        for loc1, loc2 in zip(rooms[:-1], rooms[1:]):
            start1, run1, end1 = starting_events[loc1], running_events[loc1], ending_events[loc1]
            start2, run2, end2 = starting_events[loc2], running_events[loc2], ending_events[loc2]
            line_parts += self._get_line_parts(start1, start2, end1, end2, run1, run2, fill_char=fill_char)
            if run2:
                line_parts.append(next(cards_by_id[run2.pk]))
            elif start2 or end2:
                line_parts.append(LR * col_width)
            else:
                line_parts.append(fill_char * col_width)

        room = rooms[-1]
        start, run, end = starting_events[room], running_events[room], ending_events[room]

        if start or end:
            line_parts.append(get_seperator(False, False, bool(start), bool(end)))
        elif run:
            line_parts.append(UD)
        else:
            line_parts.append(fill_char)
        return ''.join(line_parts)

    def _card(self, talk, col_width):
        empty_line = ' ' * col_width
        text_width = col_width - 4
        titlelines = textwrap.wrap(talk.submission.title, text_width)
        height = talk.duration // 5 - 1

        max_title_lines = 1 if height <= 5 else height - 4
        if len(titlelines) > max_title_lines:
            titlelines = titlelines[:max_title_lines]
            titlelines[-1] = titlelines[-1][:text_width - 1] + '…'

        speaker_str = talk.submission.display_speaker_names
        if len(speaker_str) > text_width - 4:
            speaker_str = speaker_str[:text_width-5] + '…'

        yield empty_line
        for line in titlelines:
            yield f'  \033[1m{line:<{text_width}}\033[0m  '
        for empty in range(height - len(titlelines) - 3):
            yield empty_line
        yield (f'  \033[33m{speaker_str:<{text_width-4}}\033[0m'
               f'  \033[38;5;246m{talk.submission.content_locale:<2}\033[0m  ')
        yield empty_line

    def _get_line_parts(self, start1, start2, end1, end2, run1, run2, fill_char):
        start_end = [end2, start2, start1, end1]
        result = []
        if run1 and (start2 or end2):
            result.append('├')
        elif run2 and (start1 or end1):
            result.append('┤')
        elif any(start_end):
            result.append(get_seperator(*map(bool, start_end)))
        elif run1 or run2:
            result.append(UD)
        else:
            result.append(fill_char)
        return result

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
        return HttpResponse(response_start + result, content_type='text/plain; charset=utf-8')

    def get(self, request, **kwargs):
        if 'text/html' not in request.headers.get('Accept', '') and not hasattr(self, 'is_html_export'):
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
                height_seconds = (end - start).total_seconds()
                date['display_start'] = start
                date['height_seconds'] = height_seconds
                date['height'] = int(height_seconds / 60 * 2)
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
