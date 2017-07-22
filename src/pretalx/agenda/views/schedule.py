from datetime import timedelta

from csp.decorators import csp_update
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, View


class ScheduleDataView(TemplateView):
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
        ctx['data'] = [
            {
                'index': index + 1,
                'start': current_date,
                'end': current_date + timedelta(days=1),
                'first_talk': schedule.talks.filter(start__date=current_date.date()).order_by('start').first(),
                'last_talk': schedule.talks.filter(end__date=current_date.date()).order_by('end').last(),
                'rooms': [{
                    'name': room.name,
                    'talks': [talk for talk in schedule.talks.filter(start__date=current_date.date(), room=room).order_by('start')],
                } for room in event.rooms.all()],
            } for index, current_date in enumerate([
                event.datetime_from + timedelta(days=i) for i in range((event.date_to - event.date_from).days + 1)
            ])
        ]
        for date in ctx['data']:
            date['duration'] = (date['last_talk'].end - date['first_talk'].start).seconds / 60 if date['first_talk'] else None

        return ctx


@method_decorator(csp_update(STYLE_SRC="'self', 'unsafe-inline'"), name='dispatch')
class ScheduleView(ScheduleDataView):
    template_name = 'agenda/schedule.html'


class FrabView(ScheduleDataView):
    template_name = 'agenda/schedule.xml'


class TalkView(View):
    pass
