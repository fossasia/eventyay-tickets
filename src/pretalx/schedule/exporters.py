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


class ScheduleData(BaseExporter):
    def __init__(self, event, schedule=None, with_accepted=False):
        super().__init__(event)
        self.schedule = schedule
        self.with_accepted = with_accepted

    @cached_property
    def metadata(self):
        if not self.schedule:
            return []
        return {'base_url': self.event.urls.schedule.full()}

    @cached_property
    def data(self):
        if not self.schedule:
            return []

        event = self.event
        schedule = self.schedule
        tz = pytz.timezone(event.timezone)

        base_qs = schedule.talks.all() if self.with_accepted else schedule.talks.filter(is_visible=True)
        talks = (
            base_qs
            .select_related('submission', 'submission__event', 'submission__submission_type', 'submission__track', 'room')
            .prefetch_related('submission__speakers')
            .order_by('start')
        )
        data = {
            current_date.date(): {
                'index': index + 1,
                'start': current_date.replace(hour=4, minute=0).astimezone(tz),
                'end': current_date.replace(hour=3, minute=59).astimezone(tz) + timedelta(days=1),
                'first_start': None,
                'last_end': None,
                'rooms': {},
            }
            for index, current_date in enumerate(
                event.datetime_from + timedelta(days=i)
                for i in range((event.date_to - event.date_from).days + 1)
            )
        }

        for talk in talks:
            if not talk.start or not talk.room:
                continue
            talk_date = talk.start.astimezone(tz).date()
            if talk.start.astimezone(tz).hour < 3 and talk_date != event.date_from:
                talk_date -= timedelta(days=1)
            day_data = data.get(talk_date)
            if not day_data:
                continue
            if str(talk.room.name) not in day_data['rooms']:
                day_data['rooms'][str(talk.room.name)] = {
                    'id': talk.room.id,
                    'name': talk.room.name,
                    'position': talk.room.position,
                    'talks': [talk],
                }
            else:
                day_data['rooms'][str(talk.room.name)]['talks'].append(talk)
            if not day_data['first_start'] or talk.start < day_data['first_start']:
                day_data['first_start'] = talk.start
            if not day_data['last_end'] or talk.real_end > day_data['last_end']:
                day_data['last_end'] = talk.real_end

        for d in data.values():
            d['rooms'] = sorted(
                d['rooms'].values(), key=lambda room: room['position'] if room['position'] is not None else room['id']
            )
        return data.values()


class FrabXmlExporter(ScheduleData):
    identifier = 'schedule.xml'
    verbose_name = 'XML (frab compatible)'
    public = True
    show_qrcode = True
    icon = 'fa-code'

    def render(self, **kwargs):
        context = {
            'data': self.data,
            'metadata': self.metadata,
            'schedule': self.schedule,
            'event': self.event,
            'version': __version__,
            'base_url': get_base_url(self.event),
        }
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

    def get_data(self, **kwargs):
        tz = pytz.timezone(self.event.timezone)
        schedule = self.schedule
        return {
            'version': schedule.version,
            'base_url': self.metadata['base_url'],
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
                                    'logo': talk.submission.urls.image,
                                    'date': talk.start.astimezone(tz).isoformat(),
                                    'start': talk.start.astimezone(tz).strftime(
                                        '%H:%M'
                                    ),
                                    'duration': talk.export_duration,
                                    'room': str(room['name']),
                                    'slug': talk.submission.code,
                                    'url': talk.submission.urls.public.full(),
                                    'title': talk.submission.title,
                                    'subtitle': '',
                                    'track': str(talk.submission.track.name)
                                    if talk.submission.track
                                    else None,
                                    'type': str(talk.submission.submission_type.name),
                                    'language': talk.submission.content_locale,
                                    'abstract': talk.submission.abstract,
                                    'description': talk.submission.description,
                                    'recording_license': '',
                                    'do_not_record': talk.submission.do_not_record,
                                    'persons': [
                                        {
                                            'id': person.id,
                                            'code': person.code,
                                            'public_name': person.get_display_name(),
                                            'biography': getattr(
                                                person.profiles.filter(
                                                    event=self.event
                                                ).first(),
                                                'biography',
                                                '',
                                            ),
                                            'answers': [
                                                {
                                                    'question': answer.question.id,
                                                    'answer': answer.answer,
                                                    'options': [
                                                        option.answer
                                                        for option in answer.options.all()
                                                    ],
                                                }
                                                for answer in person.answers.all()
                                            ]
                                            if getattr(self, 'is_orga', False)
                                            else [],
                                        }
                                        for person in talk.submission.speakers.all()
                                    ],
                                    'links': [],
                                    'attachments': [],
                                    'answers': [
                                        {
                                            'question': answer.question.id,
                                            'answer': answer.answer,
                                            'options': [
                                                option.answer
                                                for option in answer.options.all()
                                            ],
                                        }
                                        for answer in talk.submission.answers.all()
                                    ]
                                    if getattr(self, 'is_orga', False)
                                    else [],
                                }
                                for talk in room['talks']
                            ]
                            for room in day['rooms']
                        },
                    }
                    for day in self.data
                ],
            },
        }

    def render(self, **kwargs):
        content = self.get_data()
        return (
            f'{self.event.slug}.json'.format(self.event.slug),
            'application/json',
            json.dumps({'schedule': content}, cls=I18nJSONEncoder),
        )


class ICalExporter(BaseExporter):
    identifier = 'schedule.ics'
    verbose_name = 'iCal'
    public = True
    show_qrcode = True
    icon = 'fa-calendar'

    def __init__(self, event, schedule=None):
        super().__init__(event)
        self.schedule = schedule

    def render(self, **kwargs):
        netloc = urlparse(get_base_url(self.event)).netloc
        cal = vobject.iCalendar()
        cal.add('prodid').value = '-//pretalx//{}//'.format(netloc)
        creation_time = datetime.now(pytz.utc)

        talks = (
            self.schedule.talks.filter(is_visible=True)
            .prefetch_related('submission__speakers')
            .select_related('submission', 'room', 'submission__event')
            .order_by('start')
        )
        for talk in talks:
            talk.build_ical(cal, creation_time=creation_time, netloc=netloc)

        return f'{self.event.slug}.ics', 'text/calendar', cal.serialize()
