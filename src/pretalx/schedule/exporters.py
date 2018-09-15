import json
from datetime import datetime, timedelta
from urllib.parse import urlparse

import pytz
import vobject
from django.template.loader import get_template
from django.utils.functional import cached_property
from i18nfield.utils import I18nJSONEncoder

from pretalx import __version__
from pretalx.common.exporter import BaseExporter
from pretalx.common.urls import get_base_url
from pretalx.schedule.models import Room


class ScheduleData(BaseExporter):

    def __init__(self, event, schedule=None):
        super().__init__(event)
        self.schedule = schedule

    @cached_property
    def data(self):
        if not self.schedule:
            return []

        event = self.event
        schedule = self.schedule
        tz = pytz.timezone(event.timezone)

        talks = schedule.talks.filter(is_visible=True)\
            .select_related('submission', 'submission__event', 'room')\
            .prefetch_related('submission__speakers')\
            .order_by('start')
        rooms = Room.objects.filter(pk__in=talks.values_list('room', flat=True).distinct())
        data = [
            {
                'index': index + 1,
                'start': current_date,
                'end': current_date + timedelta(days=1),
                'first_start': min([t.start for t in talks if t.start and t.start.astimezone(tz).date() == current_date.date()] or [0]),
                'last_end': max([t.end for t in talks if t.start and t.start.astimezone(tz).date() == current_date.date()] or [0]),
                'rooms': [{
                    'name': room.name,
                    'talks': [talk for talk in talks
                              if talk.start and talk.start.astimezone(tz).date() == current_date.date() and talk.room_id == room.pk],
                } for room in rooms],
            } for index, current_date in enumerate([
                event.datetime_from + timedelta(days=i) for i in range((event.date_to - event.date_from).days + 1)
            ])
        ]
        return data


class FrabXmlExporter(ScheduleData):
    identifier = 'schedule.xml'
    verbose_name = 'XML (frab compatible)'
    public = True
    icon = 'fa-code'

    def render(self, **kwargs):
        context = {'data': self.data, 'schedule': self.schedule, 'event': self.event, 'version': __version__}
        content = get_template('agenda/schedule.xml').render(context=context)
        return f'{self.event.slug}-schedule.xml', 'text/xml', content


class FrabXCalExporter(ScheduleData):
    identifier = 'schedule.xcal'
    verbose_name = 'XCal (frab compatible)'
    public = True
    icon = 'fa-calendar'

    def render(self, **kwargs):
        url = get_base_url(self.event)
        context = {'data': self.data, 'url': url, 'domain': urlparse(url).netloc}
        content = get_template('agenda/schedule.xcal').render(context=context)
        return f'{self.event.slug}.xcal', 'text/xml', content


class FrabJsonExporter(ScheduleData):
    identifier = 'schedule.json'
    verbose_name = 'JSON (frab compatible)'
    public = True
    icon = '{ }'

    def render(self, **kwargs):
        tz = pytz.timezone(self.event.timezone)
        schedule = self.schedule
        content = {
            'version': schedule.version,
            'conference': {
                'acronym': self.event.slug,
                'title': str(self.event.name),
                'start': self.event.date_from.strftime('%Y-%m-%d'),
                'end': self.event.date_to.strftime('%Y-%m-%d'),
                'daysCount': self.event.duration,
                'timeslot_duration': '00:05',
                'days': [
                    {
                        'index': day['index'],
                        'date': day['start'].strftime('%Y-%m-%d'),
                        'day_start': day['start'].astimezone(tz).isoformat(),
                        'day_end': day['end'].astimezone(tz).isoformat(),
                        'rooms': {
                            str(room['name']): [
                                {
                                    'id': talk.submission.id,
                                    'guid': talk.submission.uuid,
                                    'logo': None,
                                    'date': talk.start.astimezone(tz).isoformat(),
                                    'start': talk.start.astimezone(tz).strftime('%H:%M'),
                                    'duration': talk.export_duration,
                                    'room': str(room['name']),
                                    'slug': talk.submission.code,
                                    'url': talk.submission.urls.public.full(),
                                    'title': talk.submission.title,
                                    'subtitle': '',
                                    'track': None,
                                    'type': str(talk.submission.submission_type.name),
                                    'language': talk.submission.content_locale,
                                    'abstract': talk.submission.abstract,
                                    'description': talk.submission.description,
                                    'recording_license': '',
                                    'do_not_record': talk.submission.do_not_record,
                                    'persons': [
                                        {
                                            'id': person.id,
                                            'name': person.get_display_name(),
                                            'biography': getattr(person.profiles.filter(event=self.event).first(), 'biography', ''),
                                            'answers': [
                                                {
                                                    'question': answer.question.id,
                                                    'answer': answer.answer,
                                                    'options': [option.answer for option in answer.options.all()],
                                                }
                                                for answer in person.answers.all()
                                            ] if getattr(self, 'is_orga', False) else [],
                                        }
                                        for person in talk.submission.speakers.all()
                                    ],
                                    'links': [],
                                    'attachments': [],
                                    'answers': [
                                        {
                                            'question': answer.question.id,
                                            'answer': answer.answer,
                                            'options': [option.answer for option in answer.options.all()],
                                        }
                                        for answer in talk.submission.answers.all()
                                    ] if getattr(self, 'is_orga', False) else [],
                                } for talk in room['talks']
                            ] for room in day['rooms']
                        }

                    } for day in self.data
                ]
            }
        }
        return f'{self.event.slug}.json'.format(self.event.slug), 'application/json', json.dumps({'schedule': content}, cls=I18nJSONEncoder)


class ICalExporter(BaseExporter):
    identifier = 'schedule.ics'
    verbose_name = 'iCal'
    public = True
    icon = 'fa-calendar'

    def __init__(self, event, schedule=None):
        super().__init__(event)
        self.schedule = schedule

    def render(self, **kwargs):
        netloc = urlparse(get_base_url(self.event)).netloc
        cal = vobject.iCalendar()
        cal.add('prodid').value = '-//pretalx//{}//'.format(netloc)
        creation_time = datetime.now(pytz.utc)

        talks = self.schedule.talks\
            .filter(is_visible=True)\
            .prefetch_related('submission__speakers')\
            .select_related('submission', 'room')\
            .order_by('start')
        for talk in talks:
            talk.build_ical(cal, creation_time=creation_time, netloc=netloc)

        return f'{self.event.slug}.ics', 'text/calendar', cal.serialize()
