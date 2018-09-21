import re
import string
import uuid

from django.conf import settings
from django.db import models
from django.utils.crypto import get_random_string
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import pgettext, ugettext_lazy as _

from pretalx.common.choices import Choices
from pretalx.common.mixins import LogMixin
from pretalx.common.models.settings import GlobalSettings
from pretalx.common.phrases import phrases
from pretalx.common.urls import EventUrls
from pretalx.mail.context import template_context_from_submission
from pretalx.submission.signals import submission_state_change


def generate_invite_code(length=32):
    return get_random_string(length=length, allowed_chars=Submission.CODE_CHARSET)


class SubmissionError(Exception):
    pass


def submission_image_path(instance, filename):
    return f'{instance.event.slug}/images/{instance.code}/{filename}'


class SubmissionStates(Choices):
    SUBMITTED = 'submitted'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
    CONFIRMED = 'confirmed'
    CANCELED = 'canceled'
    WITHDRAWN = 'withdrawn'
    DELETED = 'deleted'

    valid_choices = [
        (SUBMITTED, _('submitted')),
        (ACCEPTED, _('accepted')),
        (CONFIRMED, _('confirmed')),
        (REJECTED, _('rejected')),
        (CANCELED, _('canceled')),
        (WITHDRAWN, _('withdrawn')),
        (DELETED, _('deleted')),
    ]

    valid_next_states = {
        SUBMITTED: (REJECTED, WITHDRAWN, ACCEPTED),
        REJECTED: (ACCEPTED, SUBMITTED),
        ACCEPTED: (CONFIRMED, CANCELED, REJECTED, SUBMITTED),
        CONFIRMED: (ACCEPTED, CANCELED),
        CANCELED: (ACCEPTED, CONFIRMED),
        WITHDRAWN: (SUBMITTED),
        DELETED: tuple(),
    }

    method_names = {
        SUBMITTED: 'make_submitted',
        REJECTED: 'reject',
        ACCEPTED: 'accept',
        CONFIRMED: 'confirm',
        CANCELED: 'cancel',
        WITHDRAWN: 'withdraw',
        DELETED: 'remove',
    }


class SubmissionManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().exclude(state=SubmissionStates.DELETED)


class DeletedSubmissionManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(state=SubmissionStates.DELETED)


class AllSubmissionManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset()


class Submission(LogMixin, models.Model):
    code = models.CharField(max_length=16, unique=True)
    speakers = models.ManyToManyField(
        to='person.User', related_name='submissions', blank=True
    )
    event = models.ForeignKey(
        to='event.Event', on_delete=models.PROTECT, related_name='submissions'
    )
    title = models.CharField(max_length=200, verbose_name=_('Title'))
    submission_type = models.ForeignKey(  # Reasonable default must be set in form/view
        to='submission.SubmissionType',
        related_name='submissions',
        on_delete=models.PROTECT,
        verbose_name=_('Type of submission'),
    )
    state = models.CharField(
        max_length=SubmissionStates.get_max_length(),
        choices=SubmissionStates.get_choices(),
        default=SubmissionStates.SUBMITTED,
        verbose_name=_('Submission state'),
    )
    abstract = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('Abstract'),
        help_text=_('A concise summary of your talk in one or two sentences.')
        + ' '
        + phrases.base.use_markdown,
    )
    description = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('Description'),
        help_text=_('A full-text description of your talk and its contents.')
        + ' '
        + phrases.base.use_markdown,
    )
    notes = models.TextField(
        null=True, blank=True, verbose_name=_('Notes for the organiser')
    )
    duration = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Duration'),
        help_text=_(
            'The duration in minutes. Leave empty for default duration for this submission type.'
        ),
    )
    content_locale = models.CharField(
        max_length=32,
        default=settings.LANGUAGE_CODE,
        choices=settings.LANGUAGES,
        verbose_name=_('Language of the submission'),
    )
    is_featured = models.BooleanField(
        default=False,
        verbose_name=_(
            'Show this talk on the public sneak peek page, if it is enabled.'
        ),
    )
    do_not_record = models.BooleanField(
        default=False, verbose_name=_('Don\'t record this talk.')
    )
    image = models.ImageField(
        null=True,
        blank=True,
        upload_to=submission_image_path,
        verbose_name=_('Talk image'),
        help_text=_('Optional. Will be displayed publicly.'),
    )
    recording_url = models.CharField(
        max_length=200, null=True, blank=True, verbose_name=_('Recording URL')
    )
    recording_source = models.CharField(
        choices=(('VOC', 'media.ccc.de'),),
        max_length=3,
        null=True,
        blank=True,
        verbose_name=_('Recording Source'),
    )
    invitation_token = models.CharField(max_length=32, default=generate_invite_code)
    review_code = models.CharField(
        max_length=32, unique=True, null=True, blank=True, default=generate_invite_code
    )
    CODE_CHARSET = list('ABCDEFGHJKLMNPQRSTUVWXYZ3789')

    objects = SubmissionManager()
    deleted_objects = DeletedSubmissionManager()
    all_objects = AllSubmissionManager()

    class urls(EventUrls):
        user_base = '{self.event.urls.user_submissions}/{self.code}'
        withdraw = '{user_base}/withdraw'
        confirm = '{user_base}/confirm'
        public = '{self.event.urls.base}/talk/{self.code}'
        feedback = '{public}/feedback/'
        ical = '{public}.ics'
        image = '{self.image.url}'
        invite = '{user_base}/invite'
        accept_invitation = (
            '{self.event.urls.base}/invitation/{self.code}/{self.invitation_token}'
        )
        review = '{self.event.urls.base}/talk/review/{self.review_code}'

    class orga_urls(EventUrls):
        base = edit = '{self.event.orga_urls.submissions}/{self.code}'
        make_submitted = '{base}/submit'
        accept = '{base}/accept'
        reject = '{base}/reject'
        confirm = '{base}/confirm'
        delete = '{base}/delete'
        withdraw = '{base}/withdraw'
        cancel = '{base}/cancel'
        speakers = '{base}/speakers'
        new_speaker = '{speakers}/add'
        delete_speaker = '{speakers}/delete'
        reviews = '{base}/reviews'
        feedback = '{base}/feedback'
        toggle_featured = '{base}/toggle_featured'
        quick_schedule = '{self.event.orga_urls.schedule}/quick/{self.code}'

    def assign_code(self, length=6):
        # This omits some character pairs completely because they are hard to read even on screens (1/I and O/0)
        # and includes only one of two characters for some pairs because they are sometimes hard to distinguish in
        # handwriting (2/Z, 4/A, 5/S, 6/G).
        while True:
            code = get_random_string(length=length, allowed_chars=self.CODE_CHARSET)
            if not Submission.objects.filter(code__iexact=code).exists():
                self.code = code
                return

    def save(self, *args, **kwargs):
        if not self.code:
            self.assign_code()
        super().save(*args, **kwargs)

    @property
    def editable(self):
        return (
            self.event.cfp.is_open
            if self.state == SubmissionStates.SUBMITTED
            else self.state in (SubmissionStates.ACCEPTED, SubmissionStates.CONFIRMED)
        )

    def get_duration(self):
        if self.duration is None:
            return self.submission_type.default_duration
        return self.duration

    def _set_state(self, new_state, force=False, person=None):
        """
        Check if the new state is valid for this Submission (based on SubmissionStates.valid_next_states).

        If yes, set it and save the object. if no, raise a SubmissionError with a helpful message.
        """
        valid_next_states = SubmissionStates.valid_next_states.get(self.state, [])

        if self.state == new_state:
            return
        if new_state in valid_next_states or force:
            old_state = self.state
            self.state = new_state
            self.save(update_fields=['state'])
            submission_state_change.send_robust(
                self.event, submission=self, old_state=old_state, user=person
            )
        else:
            source_states = (
                src
                for src, dsts in SubmissionStates.valid_next_states.items()
                if new_state in dsts
            )

            # build an error message mentioning all states, which are valid source states for the desired new state.
            trans_or = pgettext(
                'used in talk confirm/accept/reject/...-errors, like "... must be accepted OR foo OR bar ..."',
                ' or ',
            )
            state_names = dict(SubmissionStates.get_choices())
            source_states = trans_or.join(
                str(state_names[state]) for state in source_states
            )
            raise SubmissionError(
                _(
                    'Submission must be {src_states} not {state} to be {new_state}.'
                ).format(
                    src_states=source_states, state=self.state, new_state=new_state
                )
            )

    def make_submitted(self, person=None, force=False, orga=False):
        self._set_state(SubmissionStates.SUBMITTED, force, person=person)
        from pretalx.schedule.models import TalkSlot

        TalkSlot.objects.filter(
            submission=self, schedule=self.event.wip_schedule
        ).delete()

    def confirm(self, person=None, force=False, orga=False):
        self._set_state(SubmissionStates.CONFIRMED, force, person=person)
        self.log_action('pretalx.submission.confirm', person=person, orga=orga)
        self.slots.filter(schedule=self.event.wip_schedule).update(is_visible=True)
        from pretalx.schedule.models import TalkSlot

        TalkSlot.objects.update_or_create(
            submission=self,
            schedule=self.event.wip_schedule,
            defaults={'is_visible': True},
        )

    def accept(self, person=None, force=False, orga=True):
        previous = self.state
        self._set_state(SubmissionStates.ACCEPTED, force, person=person)
        self.log_action('pretalx.submission.accept', person=person, orga=True)

        from pretalx.schedule.models import TalkSlot

        TalkSlot.objects.update_or_create(
            submission=self,
            schedule=self.event.wip_schedule,
            defaults={'is_visible': True},
        )

        if previous != SubmissionStates.CONFIRMED:
            for speaker in self.speakers.all():
                self.event.accept_template.to_mail(
                    user=speaker,
                    event=self.event,
                    context=template_context_from_submission(self),
                    locale=self.content_locale,
                )

    def reject(self, person=None, force=False, orga=True):
        self._set_state(SubmissionStates.REJECTED, force, person=person)
        self.log_action('pretalx.submission.reject', person=person, orga=True)

        from pretalx.schedule.models import TalkSlot

        TalkSlot.objects.filter(
            submission=self, schedule=self.event.wip_schedule
        ).delete()

        for speaker in self.speakers.all():
            self.event.reject_template.to_mail(
                user=speaker,
                event=self.event,
                context=template_context_from_submission(self),
                locale=self.content_locale,
            )

    def cancel(self, person=None, force=False, orga=True):
        self._set_state(SubmissionStates.CANCELED, force, person=person)
        self.log_action('pretalx.submission.cancel', person=person, orga=True)

        from pretalx.schedule.models import TalkSlot

        TalkSlot.objects.filter(
            submission=self, schedule=self.event.wip_schedule
        ).delete()

    def withdraw(self, person=None, force=False, orga=False):
        self._set_state(SubmissionStates.WITHDRAWN, force, person=person)
        from pretalx.schedule.models import TalkSlot

        TalkSlot.objects.filter(
            submission=self, schedule=self.event.wip_schedule
        ).delete()
        self.log_action('pretalx.submission.withdraw', person=person, orga=orga)

    def remove(self, person=None, force=False, orga=True):
        self._set_state(SubmissionStates.DELETED, force, person=person)
        for answer in self.answers.all():
            answer.remove(person=person, force=force)
        from pretalx.schedule.models import TalkSlot

        TalkSlot.objects.filter(
            submission=self, schedule=self.event.wip_schedule
        ).delete()
        self.log_action('pretalx.submission.deleted', person=person, orga=True)

    @cached_property
    def uuid(self):
        return uuid.uuid5(GlobalSettings().get_instance_identifier(), self.code)

    @cached_property
    def frab_slug(self):
        title = re.sub(r'\W+', '-', self.title)
        legal_chars = string.ascii_letters + string.digits + '-'
        pattern = f'[^{legal_chars}]+'
        title = re.sub(pattern, '', title)
        title = title.lower()
        title = title.strip('_')
        return f'{self.event.slug}-{self.pk}-{title}'

    @cached_property
    def integer_uuid(self):
        # For import into Engelsystem, we need to somehow convert our submission code into an unique integer. Luckily,
        # codes can contain 34 different characters (including compatibility with frab imported data) and normally have
        # 6 charactes. Since log2(34 **6) == 30.52, that just fits in to a positive 32-bit signed integer (that
        # Engelsystem expects), if we do it correctly.
        charset = self.CODE_CHARSET + [
            '1',
            '2',
            '4',
            '5',
            '6',
            '0',
        ]  # compatibility with imported frab data
        base = len(charset)
        table = {char: i for i, char in enumerate(charset)}

        intval = 0
        for char in self.code:
            intval *= base
            intval += table[char]
        return intval

    @property
    def slot(self):
        if self.event.current_schedule:
            return self.event.current_schedule.talks.filter(submission=self).first()

    @property
    def display_speaker_names(self):
        return ', '.join(speaker.get_display_name() for speaker in self.speakers.all())

    @property
    def does_accept_feedback(self):
        slot = self.slot
        if slot and slot.start:
            end = slot.end or slot.start + slot.submission.get_duration()
            return end < now()
        return False

    @cached_property
    def rendered_recording_iframe(self):
        if not (self.recording_url and self.recording_source):
            return
        from django.template import engines

        django_engine = engines['django']
        template = django_engine.from_string(
            '<div class="embed-responsive embed-responsive-16by9"><iframe src="{{ url }}" frameborder="0" allowfullscreen></iframe></div>'
        )
        return template.render(context={'url': self.recording_url})

    @property
    def average_score(self):
        return self.reviews.all().aggregate(avg=models.Avg('score'))['avg']

    @property
    def active_resources(self):
        return self.resources.filter(resource__isnull=False)

    @property
    def is_deleted(self):
        return self.state == SubmissionStates.DELETED

    def __str__(self):
        """Help when debugging."""
        return f'Submission(event={self.event.slug}, code={self.code}, title={self.title}, state={self.state})'

    @cached_property
    def export_duration(self):
        from pretalx.common.serialize import serialize_duration

        return serialize_duration(minutes=self.get_duration())

    @cached_property
    def speaker_profiles(self):
        from pretalx.person.models.profile import SpeakerProfile

        return SpeakerProfile.objects.filter(
            event=self.event, user__in=self.speakers.all()
        )

    @property
    def availabilities(self):
        from pretalx.schedule.models.availability import Availability

        all_availabilities = self.event.availabilities.filter(
            person__in=self.speaker_profiles
        )
        return Availability.intersection(all_availabilities)
