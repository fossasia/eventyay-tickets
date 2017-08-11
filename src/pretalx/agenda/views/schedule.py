from datetime import timedelta

import pytz
from csp.decorators import csp_update
from django.utils.decorators import method_decorator
from django.views.generic import DetailView, TemplateView

from pretalx.cfp.views.event import EventPageMixin
from pretalx.submission.models import Submission


def day_start(dt):
    return dt.replace(hour=0, minute=0, second=0)


def day_end(dt):
    return dt.replace(hour=23, minute=59, second=59)


class ScheduleDataView(EventPageMixin, TemplateView):
    template_name = 'agenda/schedule.html'

    def get_object(self):
        if self.request.GET.get('version'):
            return self.request.event.schedules.filter(version=self.request.GET.get('version'))
        return self.request.event.current_schedule

    def get_context_data(self, event):
        ctx = super().get_context_data()
        schedule = self.get_object()
        event = self.request.event

        if not schedule and self.request.GET.get('version'):
            ctx['version'] = self.request.GET.get('version')
            ctx['error'] = 'wrong-version'
            return ctx
        elif not schedule:
            ctx['error'] = 'no-schedule'
            return ctx
        ctx['schedule'] = schedule
        ctx['schedules'] = event.schedules.filter(published__isnull=False).values_list('version')
        talks = schedule.talks.filter(is_visible=True)

        ctx['data'] = [
            {
                'index': index + 1,
                'start': current_date,
                'end': current_date + timedelta(days=1),
                'first_talk': talks.filter(
                    start__gte=day_start(current_date), start__lte=day_end(current_date)
                ).order_by('start').first(),
                'last_talk': talks.filter(
                    start__gte=day_start(current_date), start__lte=day_end(current_date)
                ).order_by('end').last(),
                'rooms': [{
                    'name': room.name,
                    'talks': [talk for talk in talks.filter(
                        start__gte=day_start(current_date), start__lte=day_end(current_date), room=room
                    ).order_by('start')],
                } for room in event.rooms.all()],
            } for index, current_date in enumerate([
                event.datetime_from + timedelta(days=i) for i in range((event.date_to - event.date_from).days + 1)
            ])
        ]
        return ctx


@method_decorator(csp_update(STYLE_SRC="'self' 'unsafe-inline'"), name='dispatch')
class ScheduleView(ScheduleDataView):
    template_name = 'agenda/schedule.html'

    def get_object(self):
        obj = super().get_object()
        if not obj and self.request.is_orga:
            return self.request.event.wip_schedule
        return obj

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        tz = pytz.timezone(self.request.event.timezone)
        if 'data' in ctx:
            for date in ctx['data']:
                if date.get('first_talk') and date.get('last_talk'):
                    start = date.get('first_talk').start.astimezone(tz).replace(second=0, minute=0)
                    end = date.get('last_talk').end.astimezone(tz)
                    date['height'] = int((end - start).seconds / 60 * 2)
                    date['hours'] = []
                    d = start
                    while d < end:
                        date['hours'].append(d.strftime('%H:%M'))
                        d += timedelta(hours=1)
                    for room in date['rooms']:
                        for talk in room.get('talks', []):
                            talk.top = int((talk.start.astimezone(tz) - start).seconds / 60 * 2)
                            talk.height = talk.duration * 2
        return ctx


class FrabView(ScheduleDataView):
    template_name = 'agenda/schedule.xml'


class TalkView(DetailView):
    context_object_name = 'talk'
    model = Submission
    slug_field = 'code'
    template_name = 'agenda/talk.html'

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['speakers'] = []
        for speaker in self.object.speakers.all():  # TODO: there's bound to be an elegant annotation for this
            speaker.talk_profile = speaker.profiles.filter(event=self.request.event).first()
            ctx['speakers'].append(speaker)
        return ctx


class ChangelogView(TemplateView):
    template_name = 'agenda/changelog.html'
