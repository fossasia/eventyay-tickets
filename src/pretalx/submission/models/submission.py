import re
import statistics
import string
import uuid
import warnings
from contextlib import suppress
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models.fields.files import FieldFile
from django.utils.crypto import get_random_string
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import pgettext, ugettext_lazy as _

from pretalx.common.choices import Choices
from pretalx.common.mixins import LogMixin
from pretalx.common.phrases import phrases
from pretalx.common.urls import EventUrls
from pretalx.mail.context import template_context_from_submission
from pretalx.mail.models import QueuedMail
from pretalx.submission.signals import submission_state_change

INSTANCE_IDENTIFIER = None
with suppress(Exception):
    from pretalx.common.models.settings import GlobalSettings
    INSTANCE_IDENTIFIER = GlobalSettings().get_instance_identifier()


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
    pass


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
        verbose_name=_('Submission type'),
    )
    track = models.ForeignKey(
        to='submission.Track',
        related_name='submissions',
        on_delete=models.PROTECT,
        verbose_name=_('Track'),
        null=True,
        blank=True,
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
        help_text=phrases.base.use_markdown,
    )
    description = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('Description'),
        help_text=phrases.base.use_markdown,
    )
    notes = models.TextField(
        null=True, blank=True, verbose_name=_('Notes'),
        help_text=_('These notes are meant for the organiser and won\'t be made public.'),
    )
    internal_notes = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('Internal notes'),
        help_text=_('Internal notes for other organisers/reviewers. Not visible to the speakers or the public.')
    )
    duration = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Duration'),
        help_text=_(
            'The duration in minutes. Leave empty for default duration for this submission type.'
        ),
    )
    slot_count = models.PositiveIntegerField(
        default=1,
        verbose_name=_('Slot Count'),
        help_text=_(
            'How many times this talk will be held.'
        ),
    )
    content_locale = models.CharField(
        max_length=32,
        default=settings.LANGUAGE_CODE,
        choices=settings.LANGUAGES,
        verbose_name=_('Language'),
    )
    is_featured = models.BooleanField(
        default=False,
        verbose_name=_(
            'Show this talk on the public sneak peek page, if the sneak peek page is enabled and the talk was accepted.'
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
        help_text=_('Use this if you want an illustration to go with your submission.'),
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
        user_base = '{self.event.urls.user_submissions}{self.code}/'
        withdraw = '{user_base}withdraw'
        confirm = '{user_base}confirm'
        public_base = '{self.event.urls.base}talk/{self.code}'
        public = '{public_base}/'
        feedback = '{public}feedback/'
        ical = '{public_base}.ics'
        image = '{self.image_url}'
        invite = '{user_base}invite'
        accept_invitation = (
            '{self.event.urls.base}invitation/{self.code}/{self.invitation_token}'
        )
        review = '{self.event.urls.base}talk/review/{self.review_code}'

    class orga_urls(EventUrls):
        base = edit = '{self.event.orga_urls.submissions}{self.code}/'
        make_submitted = '{base}submit'
        accept = '{base}accept'
        reject = '{base}reject'
        confirm = '{base}confirm'
        delete = '{base}delete'
        withdraw = '{base}withdraw'
        cancel = '{base}cancel'
        speakers = '{base}speakers/'
        new_speaker = '{speakers}add'
        delete_speaker = '{speakers}delete'
        reviews = '{base}reviews/'
        feedback = '{base}feedback/'
        toggle_featured = '{base}toggle_featured'
        quick_schedule = '{self.event.orga_urls.schedule}quick/{self.code}/'

    @property
    def image_url(self):
        return self.image.url if self.image else ''

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
        if self.state == SubmissionStates.SUBMITTED:
            return self.event.cfp.is_open or (self.event.active_review_phase and self.event.active_review_phase.speakers_can_change_submissions)
        return self.state in (SubmissionStates.ACCEPTED, SubmissionStates.CONFIRMED)

    def get_duration(self):
        if self.duration is None:
            return self.submission_type.default_duration
        return self.duration

    def update_duration(self):
        for slot in self.event.wip_schedule.talks.filter(
            submission=self, start__isnull=False
        ):
            slot.end = slot.start + timedelta(minutes=self.get_duration())
            slot.save()

    def _set_state(self, new_state, force=False, person=None):
        """
        Check if the new state is valid for this Submission (based on SubmissionStates.valid_next_states).

        If yes, set it and save the object. if no, raise a SubmissionError with a helpful message.
        """
        valid_next_states = SubmissionStates.valid_next_states.get(self.state, [])

        if self.state == new_state:
            self.update_talk_slots()
            return
        if force or new_state in valid_next_states:
            old_state = self.state
            self.state = new_state
            self.save(update_fields=['state'])
            self.update_talk_slots()
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

    def update_talk_slots(self):
        from pretalx.schedule.models import TalkSlot

        if self.state not in [SubmissionStates.ACCEPTED, SubmissionStates.CONFIRMED]:
            TalkSlot.objects.filter(
                submission=self, schedule=self.event.wip_schedule
            ).delete()
            return

        slot_count_current = TalkSlot.objects.filter(
            submission=self,
            schedule=self.event.wip_schedule,
        ).count()
        diff = slot_count_current - self.slot_count

        if diff > 0:
            # We build a list of all IDs to delete as .delete() doesn't work on sliced querysets.
            # We delete unscheduled talks first.
            talks_to_delete = TalkSlot.objects.filter(
                submission=self,
                schedule=self.event.wip_schedule,
                room__isnull=True,
                start__isnull=True,
            ).order_by('start', 'is_visible')[:diff].values_list("id", flat=True)
            TalkSlot.objects.filter(pk__in=list(talks_to_delete)).delete()
        elif diff < 0:
            for index in range(abs(diff)):
                TalkSlot.objects.create(
                    submission=self,
                    schedule=self.event.wip_schedule,
                )

    def make_submitted(self, person=None, force=False, orga=False):
        self._set_state(SubmissionStates.SUBMITTED, force, person=person)

    def confirm(self, person=None, force=False, orga=False):
        self._set_state(SubmissionStates.CONFIRMED, force, person=person)
        self.log_action('pretalx.submission.confirm', person=person, orga=orga)

    def accept(self, person=None, force=False, orga=True):
        previous = self.state
        self._set_state(SubmissionStates.ACCEPTED, force, person=person)
        self.log_action('pretalx.submission.accept', person=person, orga=True)

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

    def withdraw(self, person=None, force=False, orga=False):
        self._set_state(SubmissionStates.WITHDRAWN, force, person=person)
        self.log_action('pretalx.submission.withdraw', person=person, orga=orga)

    def remove(self, person=None, force=False, orga=True):
        self._set_state(SubmissionStates.DELETED, force, person=person)
        for answer in self.answers.all():
            answer.remove(person=person, force=force)
        self.log_action('pretalx.submission.deleted', person=person, orga=True)

    @cached_property
    def uuid(self):
        global INSTANCE_IDENTIFIER
        if not INSTANCE_IDENTIFIER:
            from pretalx.common.models.settings import GlobalSettings
            INSTANCE_IDENTIFIER = GlobalSettings().get_instance_identifier()
        return uuid.uuid5(INSTANCE_IDENTIFIER, self.code)

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

    @cached_property
    def slot(self):
        return (
            self.event.current_schedule.talks.filter(submission=self).first()
            if self.event.current_schedule
            else None
        )

    @cached_property
    def display_speaker_names(self):
        return ', '.join(speaker.get_display_name() for speaker in self.speakers.all())

    @cached_property
    def does_accept_feedback(self):
        slot = self.slot
        if slot and slot.start:
            end = slot.end or slot.start + slot.submission.get_duration()
            return end < now()
        return False

    @cached_property
    def rendered_recording_iframe(self):
        if self.recording_url and self.recording_source:
            warnings.warn(
                'Please use a recording source plugin instead of pretalx core functionality.',
                DeprecationWarning,
            )
            from django.template import engines

            django_engine = engines['django']
            template = django_engine.from_string(
                '<div class="embed-responsive embed-responsive-16by9"><iframe src="{{ url }}" frameborder="0" allowfullscreen></iframe></div>'
            )
            return template.render(context={'url': self.recording_url})

    @cached_property
    def median_score(self):
        scores = [r.score for r in self.reviews.all() if r.score is not None]
        return statistics.median(scores) if scores else None

    @cached_property
    def active_resources(self):
        return self.resources.exclude(resource=None).exclude(resource="")

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

    @cached_property
    def created(self):
        return getattr(
            self.logged_actions().order_by('timestamp').first(), 'timestamp', None
        )

    def get_content_for_mail(self):
        order = ['title', 'abstract', 'description', 'notes', 'duration', 'content_locale', 'do_not_record', 'image']
        data = []
        result = ''
        for field in order:
            field_content = getattr(self, field, None)
            if field_content:
                _field = self._meta.get_field(field)
                field_name = _field.verbose_name or _field.name
                data.append({'name': field_name, 'value': field_content})
        for answer in self.answers.all():
            if answer.answer:
                data.append({'name': answer.question.question, 'value': answer.answer})
            elif answer.answer_file:
                data.append({'name': answer.question.question, 'value': answer.answer_file})
        for content in data:
            field_name = content['name']
            field_content = content['value']
            if isinstance(field_content, bool):
                field_content = _('Yes') if field_content else _('No')
            elif isinstance(field_content, FieldFile):
                field_content = (self.event.settings.custom_domain or settings.SITE_URL) + field_content.url
            result += f'**{field_name}**: {field_content}\n\n'
        return result

    def send_invite(self, to, _from=None, subject=None, text=None):
        if not _from and (not subject or not text):
            raise Exception('Please tell me how to sign this invitation.')

        subject = subject or _('{speaker} invites you to join their talk!').format(
            speaker=_from.get_display_name()
        )
        subject = f'[{self.event.slug}] {subject}'
        text = text or _(
            '''Hi!

I'd like to invite you to be a speaker in the talk

  “{title}”

at {event}. Please follow this link to join:

  {url}

I'm looking forward to it!
{speaker}'''
        ).format(
            event=self.event.name,
            title=self.title,
            url=self.urls.accept_invitation.full(),
            speaker=_from.get_display_name(),
        )
        to = to.split(',') if isinstance(to, str) else to
        for invite in to:
            QueuedMail(
                event=self.event,
                to=invite,
                subject=subject,
                text=text,
            ).send()
