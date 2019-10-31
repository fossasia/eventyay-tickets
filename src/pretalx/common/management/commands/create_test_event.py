import datetime as dt
import random
import re

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from pretalx.common.tasks import regenerate_css
from pretalx.event.models import Event, Team
from pretalx.event.utils import create_organiser_with_team
from pretalx.person.models import SpeakerProfile, User
from pretalx.schedule.models import Room
from pretalx.submission.models import Review, Submission, SubmissionType, Track


class Command(BaseCommand):
    help = 'Create a test event'

    def add_arguments(self, parser):
        parser.add_argument('--stage', type=str, default='schedule', help='Up to which stage should this event be created? Choices, in logical order, are "cfp", "review", "schedule", "over". The default is "schedule".')

    def build_event(self, end_stage):
        administrators = User.objects.filter(is_administrator=True)
        if not administrators:
            self.stdout.write(self.style.ERROR('Please run the "init" command to create an administrator user.'))
            return
        organiser, team = create_organiser_with_team(
            name='DemoCon Org',
            slug='democonorg',
            users=administrators,
        )
        if end_stage == 'cfp':
            event_start = now() + dt.timedelta(days=35)
        elif end_stage == 'review':
            event_start = now() + dt.timedelta(days=25)
        elif end_stage == 'over':
            event_start = now() - dt.timedelta(days=10)
        else:  # end_stage == 'schedule'
            event_start = now() - dt.timedelta(days=1)
        self.bs = self.fake.bs()
        self.catch_phrase = self.fake.catch_phrase()
        intro = f'We provide a {self.catch_phrase.lower()} to {self.bs}.'
        disclaimer = '''This is an automatically generated event to test and showcase pretalx features.
Feel free to look around, but don\'t be alarmed if something doesn\'t quite make sense. You can always create your own free test event at [pretalx.com](https://pretalx.com)!'''
        with scopes_disabled():
            event = Event.objects.create(
                name='DemoCon',
                slug='democon',
                organiser=organiser,
                is_public=True,
                date_from=event_start.date(),
                date_to=event_start.date() + dt.timedelta(days=2),
                timezone='Europe/Berlin',
                email=self.fake.user_name() + '@example.org',
                primary_color=self.fake.hex_color(),
                locale_array='en',
                locale='en',
                landing_page_text=f'# Welcome to DemoCon!\n\n{intro}\n\n{disclaimer}',
            )
        with scope(event=event):
            event.build_initial_data()
            team.limit_events.add(event)
            SubmissionType.objects.create(event=event, name='Workshop', default_duration=90)

            event.settings.use_tracks = True
            for _ in range(self.fake.random_int(min=2, max=5)):
                Track.objects.create(
                    event=event,
                    name=self.fake.catch_phrase().split()[0],
                    color=self.fake.hex_color(),
                )
            event.cfp.headline = 'DemoCon submissions are {}!'.format('open' if end_stage == 'cfp' else 'closed')
            track_text = '\n'.join(f'- {track.name}' for track in event.tracks.all())
            event.cfp.text = f'''This is the Call for Participation for DemoCon!\n\n{intro}\n\n

We are always on the look-out for speakers who can provide {self.fake.bs()} – if that is you, please submit a talk or a workshop! We accept submissions for the following tracks:

{track_text}

We explicitly encourage new speakers and multiple submissions per person.
If you have any interest in {self.fake.catch_phrase().lower()}, {self.fake.catch_phrase().lower()}, {self.fake.catch_phrase().lower()} – or something else you think matches our conference, please submit your proposal!

{disclaimer}
'''
            event.cfp.deadline = event.datetime_from - dt.timedelta(days=60)
            event.cfp.save()
            event.settings.display_header_pattern = random.choice(
                ('', 'pcb', 'bubbles', 'signal', 'topo', 'graph')
            )
            event.settings.review_max_score = 2
            self.event = event
            self.build_room()
            self.build_room()
            regenerate_css(event.pk)
        return event

    def build_room(self):
        name = ' '.join([a for a in re.split(r'([A-Z][a-z]*\d*)', self.fake.color_name()) if a])
        return Room.objects.create(event=self.event, name=f'{name} Room', position=self.fake.random_digit())

    def build_cfp_stage(self):
        """Targeting 53-85 total submissions, with at least some speakers with
        double submissions and some with multiple speakers.

        Submissions are distributed across the submission timeline in a
        realistic fashion.
        """
        target_talk_submissions = self.fake.random_int(min=40, max=65)
        target_workshop_submissions = self.fake.random_int(min=13, max=20)
        total_submissions = target_talk_submissions + target_workshop_submissions
        target_speaker_count = self.fake.random_int(
            min=int(total_submissions / 1.8),
            max=int(total_submissions / 1.1),
        )
        speakers = [self.build_speaker() for _ in range(target_speaker_count)]
        for _ in range(total_submissions - target_speaker_count):
            speakers.append(random.choice(speakers))

        submission_times = []
        max_submission_time = min(now(), self.event.cfp.deadline)
        for _ in range(int(total_submissions / 10)):
            submission_times.append(self.fake.date_time_between_dates(
                datetime_start=max_submission_time - dt.timedelta(days=20),
                datetime_end=max_submission_time - dt.timedelta(days=7),
            ))
        for _ in range(int(total_submissions / 20)):
            submission_times.append(self.fake.date_time_between_dates(
                datetime_start=max_submission_time - dt.timedelta(days=7),
                datetime_end=max_submission_time - dt.timedelta(days=3),
            ))
        for _ in range(int(total_submissions / 20)):
            submission_times.append(self.fake.date_time_between_dates(
                datetime_start=max_submission_time - dt.timedelta(days=3),
                datetime_end=max_submission_time - dt.timedelta(days=1),
            ))
        while len(submission_times) < total_submissions:
            submission_times.append(self.fake.date_time_between_dates(
                datetime_start=max_submission_time - dt.timedelta(days=1),
                datetime_end=max_submission_time,
            ))
        talk = self.event.submission_types.get(name__iexact='talk')
        workshop = self.event.submission_types.get(name__iexact='workshop')
        submission_types = [workshop for _ in range(target_workshop_submissions)] + [talk for _ in range(target_talk_submissions)]
        random.shuffle(submission_types)
        submissions = [
            self.build_submission(speaker, submission_type, submission_time)
            for speaker, submission_type, submission_time
            in zip(speakers, submission_types, submission_times)
        ]
        for _ in range(self.fake.random_int(min=5, max=15)):
            submission = random.choice(submissions)
            speaker = random.choice(speakers)
            submission.speakers.add(speaker)

    def build_speaker(self):
        user = User.objects.create_user(
            name=self.fake.name(),
            email=self.fake.user_name() + '@example.org',
            locale='en',
            timezone='Europe/Berlin',
            # TODO: generate avatar,
        )
        SpeakerProfile.objects.create(
            user=user, event=self.event,
            biography='\n\n'.join(self.fake.texts(2))
        )
        return user

    def build_submission(self, speaker, submission_type, submission_time):
        with self.freeze_time(submission_time):
            submission = Submission.objects.create(
                event=self.event,
                title=self.fake.catch_phrase(),
                submission_type=submission_type,
                track=random.choice(self.event.tracks.all()),
                abstract=self.fake.bs().capitalize() + '!',
                description=self.fake.text(),
                content_locale='en',
                do_not_record=random.choice([False] * 10 + [True]),
            )
            submission.log_action('pretalx.submission.create', person=speaker)
        submission.speakers.add(speaker)
        return submission

    def build_review_stage(self):
        """We will go with only three reviewers: One to review all submissions,
        one to review more positively, one to review more negatively."""
        reviewers = [
            User.objects.create_user(
                name=self.fake.name(),
                email=self.fake.user_name() + '@example.org',
                locale='en',
                timezone='Europe/Berlin',
            ) for _ in range(3)
        ]
        team = Team.objects.create(organiser=self.event.organiser, name='DemoCon Reviewers', is_reviewer=True)
        team.limit_events.add(self.event)
        all_submissions = list(self.event.submissions.all())

        reviewer = reviewers[0]
        for submission in all_submissions:
            self.build_review(reviewer, submission)

        random.shuffle(all_submissions)
        reviewer = reviewers[1]
        for submission in all_submissions[:(int(len(all_submissions) * 0.8))]:
            self.build_review(reviewer, submission, positive=True)

        random.shuffle(all_submissions)
        reviewer = reviewers[2]
        for submission in all_submissions[:(int(len(all_submissions) * 0.6))]:
            self.build_review(reviewer, submission, positive=False)

        all_talks = sorted(list(self.event.submissions.filter(submission_type__name='Talk')), key=lambda x: x.median_score, reverse=True)
        all_workshops = sorted(list(self.event.submissions.filter(submission_type__name='Workshop')), key=lambda x: x.median_score, reverse=True)

        for index, talk in enumerate(all_talks):
            if index < 27:
                talk.accept()
                talk.confirm()
            else:
                talk.reject()

        for index, talk in enumerate(all_workshops):
            if index < 9:
                talk.accept()
                talk.confirm()
            else:
                talk.reject()

    def build_review(self, reviewer, submission, positive=None):
        rating = [0, 1, 2]
        if positive is True:
            rating.append(2)
        elif positive is False:
            rating.append(0)
        return Review.objects.create(
            submission=submission,
            user=reviewer,
            score=random.choice(rating)
        )

    def build_schedule_stage(self):
        # Three days, two rooms, nine talks and three workshops and day == 3 * 12 = 36 slots
        talks = (_ for _ in self.event.submissions.filter(state='confirmed', submission_type__name='Talk'))
        workshops = (_ for _ in self.event.submissions.filter(state='confirmed', submission_type__name='Workshop'))
        talk_room, workshop_room = self.event.rooms.all()
        current_time = self.event.datetime_from + dt.timedelta(hours=9)

        def schedule_slot(submission, time, room):
            slot = submission.slots.first()
            slot.start = time
            slot.end = time + dt.timedelta(minutes=submission.submission_type.default_duration)
            slot.room = room
            slot.save()

        def build_block():
            nonlocal current_time
            schedule_slot(next(workshops), current_time, workshop_room)
            for _ in range(3):
                schedule_slot(next(talks), current_time, talk_room)
                current_time += dt.timedelta(minutes=30)

        for _ in range(3):
            for _ in range(3):
                build_block()
                current_time += dt.timedelta(minutes=60)
            current_time += dt.timedelta(hours=16, minutes=30)
        self.event.wip_schedule.freeze('v1.0')

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            from faker import Faker
            self.fake = Faker()
        except ImportError:
            self.stdout.write(self.style.ERROR('Please run "pip install Faker" to use this command.'))
            return

        try:
            from freezegun import freeze_time
            self.freeze_time = freeze_time
        except ImportError:
            self.stdout.write(self.style.ERROR('Please run "pip install freezegun" to use this command.'))
            return

        end_stage = options.get('stage')
        event = self.build_event(end_stage)
        if not event:
            return
        with scope(event=event):
            for stage in ("cfp", "review", "schedule"):
                getattr(self, f"build_{stage}_stage")()
                self.stdout.write(self.style.SUCCESS(f'Built data for stage "{stage}".'))
                if end_stage == stage:
                    return
