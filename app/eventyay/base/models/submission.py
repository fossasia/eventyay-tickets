import copy
import datetime as dt
import json
import statistics
from itertools import repeat

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import JSONField, Q
from django.db.models.fields.files import FieldFile
from django.shortcuts import get_object_or_404
from django.utils.crypto import get_random_string
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext_lazy as _n
from django.utils.translation import override, pgettext_lazy
from django_scopes import ScopedManager, scopes_disabled
from rest_framework import serializers

from eventyay.base.models import Choices, User
from eventyay.common.exceptions import SubmissionError
from eventyay.common.text.path import path_with_hash
from eventyay.common.text.phrases import phrases
from eventyay.common.text.serialize import serialize_duration
from eventyay.common.urls import EventUrls
from eventyay.submission.signals import submission_state_change
from eventyay.talk_rules.agenda import (
    event_uses_feedback,
    is_agenda_submission_visible,
    is_agenda_visible,
)
from eventyay.talk_rules.person import is_reviewer
from eventyay.talk_rules.submission import (
    are_featured_submissions_visible,
    can_be_accepted,
    can_be_canceled,
    can_be_confirmed,
    can_be_edited,
    can_be_rejected,
    can_be_removed,
    can_be_reviewed,
    can_be_withdrawn,
    can_request_speakers,
    can_view_reviews,
    has_reviewer_access,
    is_feedback_ready,
    is_speaker,
    orga_can_change_submissions,
    orga_or_reviewer_can_change_submission,
)

from .mixins import GenerateCode, PretalxModel


def generate_invite_code(length=32):
    return get_random_string(length=length, allowed_chars=Submission._code_charset)


def submission_image_path(instance, filename):
    return path_with_hash(filename, base_path=f'{instance.event.slug}/submissions/{instance.code}/')


class SubmissionStates(Choices):
    SUBMITTED = 'submitted'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
    CONFIRMED = 'confirmed'
    CANCELED = 'canceled'
    WITHDRAWN = 'withdrawn'
    DELETED = 'deleted'
    DRAFT = 'draft'

    display_values = {
        SUBMITTED: pgettext_lazy('proposal status', 'submitted'),
        ACCEPTED: _('accepted'),
        CONFIRMED: _('confirmed'),
        REJECTED: _('rejected'),
        CANCELED: _('canceled'),
        WITHDRAWN: _('withdrawn'),
        DELETED: _('deleted'),
        DRAFT: _('draft'),
    }
    valid_choices = [(key, value) for key, value in display_values.items()]

    valid_next_states = {
        SUBMITTED: (REJECTED, WITHDRAWN, ACCEPTED),
        REJECTED: (ACCEPTED, SUBMITTED),
        ACCEPTED: (CONFIRMED, CANCELED, REJECTED, SUBMITTED, WITHDRAWN),
        CONFIRMED: (ACCEPTED, CANCELED),
        CANCELED: (ACCEPTED, CONFIRMED),
        WITHDRAWN: (SUBMITTED),
        DELETED: (),
        DRAFT: (SUBMITTED,),
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

    accepted_states = (ACCEPTED, CONFIRMED)

    @staticmethod
    def get_color(state):
        return {
            SubmissionStates.SUBMITTED: '--color-info',
            SubmissionStates.ACCEPTED: '--color-success',
            SubmissionStates.CONFIRMED: '--color-success',
            SubmissionStates.REJECTED: '--color-danger',
        }.get(state, '--color-grey')


class SubmissionManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().exclude(state=SubmissionStates.DELETED).exclude(state=SubmissionStates.DRAFT)


class DeletedSubmissionManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(state=SubmissionStates.DELETED)


class AllSubmissionManager(models.Manager):
    pass


class SpeakerRole(models.Model):
    """Through model connecting speaker and submission."""

    submission = models.ForeignKey(
        to='Submission',
        on_delete=models.CASCADE,
        related_name='speaker_roles',
    )
    user = models.ForeignKey(to='User', on_delete=models.CASCADE, related_name='speaker_roles')

    objects = ScopedManager(event='submission__event')

    class Meta:
        unique_together = (('submission', 'user'),)

    def __str__(self):
        return f'SpeakerRole(submission={self.submission.code}, speaker={self.user})'


class Submission(GenerateCode, PretalxModel):
    """Submissions are, next to :class:`~pretalx.event.models.event.Event`, the
    central model in pretalx.

    A submission, which belongs to exactly one event, can have multiple
    speakers and a lot of other related data, such as a
    :class:`~pretalx.submission.models.type.SubmissionType`, a
    :class:`~pretalx.submission.models.track.Track`, multiple
    :class:`~pretalx.submission.models.question.Answer` objects, and so on.

    :param code: The unique alphanumeric identifier used to refer to a
        submission.
    :param state: The submission can be 'submitted', 'accepted', 'confirmed',
        'rejected', 'withdrawn', or 'canceled'. State changes should be done via
        the corresponding methods, like ``accept()``. The ``SubmissionStates``
        class comes with a ``method_names`` dictionary for method lookup.
    :param image: An image illustrating the talk or topic.
    :param review_code: A token used in secret URLs giving read-access to the
        submission.
    """

    code = models.CharField(max_length=16, unique=True)
    speakers = models.ManyToManyField(
        to='User',
        related_name='submissions',
        through=SpeakerRole,
        blank=True,
    )
    event = models.ForeignKey(to='Event', on_delete=models.PROTECT, related_name='submissions')
    title = models.CharField(max_length=200, verbose_name=_('Proposal title'))
    submission_type = models.ForeignKey(  # Reasonable default must be set in form/view
        to='SubmissionType',
        related_name='submissions',
        on_delete=models.PROTECT,
        verbose_name=_('Session type'),
    )
    track = models.ForeignKey(
        to='Track',
        related_name='submissions',
        on_delete=models.PROTECT,
        verbose_name=_('Track'),
        null=True,
        blank=True,
    )
    tags = models.ManyToManyField(
        to='Tag',
        related_name='submissions',
        verbose_name=_('Tags'),
    )
    state = models.CharField(
        max_length=SubmissionStates.get_max_length(),
        choices=SubmissionStates.get_choices(),
        default=SubmissionStates.SUBMITTED,
        verbose_name=_('Proposal state'),
    )
    pending_state = models.CharField(
        null=True,
        blank=True,
        max_length=SubmissionStates.get_max_length(),
        choices=SubmissionStates.get_choices(),
        default=None,
        verbose_name=_('Pending proposal state'),
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
        null=True,
        blank=True,
        verbose_name=_('Notes'),
        help_text=_('These notes are meant for the organiser and won’t be made public.'),
    )
    internal_notes = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('Internal notes'),
        help_text=_('Internal notes for other organisers/reviewers. Not visible to the speakers or the public.'),
    )
    duration = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Duration'),
        help_text=_('The duration in minutes.'),
    )
    slot_count = models.IntegerField(
        default=1,
        verbose_name=_('Slot Count'),
        help_text=_('How many times this session will take place.'),
        validators=[MinValueValidator(1)],
    )
    content_locale = models.CharField(
        max_length=32,
        default=settings.LANGUAGE_CODE,
        verbose_name=_('Language'),
    )
    is_featured = models.BooleanField(
        default=False,
        verbose_name=_('Show this session in public list of featured sessions.'),
    )
    do_not_record = models.BooleanField(default=False, verbose_name=_('Don’t record this session.'))
    image = models.ImageField(
        null=True,
        blank=True,
        upload_to=submission_image_path,
        verbose_name=_('Session image'),
        help_text=_('Use this if you want an illustration to go with your proposal.'),
    )
    invitation_token = models.CharField(max_length=32, default=generate_invite_code)
    access_code = models.ForeignKey(
        to='SubmitterAccessCode',
        related_name='submissions',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    review_code = models.CharField(max_length=32, unique=True, null=True, blank=True, default=generate_invite_code)
    anonymised_data = models.TextField(null=True, blank=True, default='{}')
    assigned_reviewers = models.ManyToManyField(
        verbose_name=_('Assigned reviewers'),
        to='User',
        related_name='assigned_reviews',
        blank=True,
    )

    objects = ScopedManager(event='event', _manager_class=SubmissionManager)
    deleted_objects = ScopedManager(event='event', _manager_class=DeletedSubmissionManager)
    all_objects = ScopedManager(event='event', _manager_class=AllSubmissionManager)

    log_prefix = 'pretalx.submission'

    class Meta:
        rules_permissions = {
            'list': is_agenda_visible | orga_can_change_submissions | is_reviewer,
            'list_featured': are_featured_submissions_visible | orga_can_change_submissions,
            'view': is_agenda_submission_visible | is_speaker | orga_can_change_submissions | has_reviewer_access,
            'view_public': is_agenda_submission_visible | orga_can_change_submissions,
            'orga_list': orga_can_change_submissions | is_reviewer,
            'orga_update': orga_can_change_submissions,
            'review': has_reviewer_access & can_be_reviewed,
            'view_reviews': has_reviewer_access | orga_can_change_submissions,
            'view_all_reviews': (has_reviewer_access & can_view_reviews) | orga_can_change_submissions,
            'create': orga_can_change_submissions,
            'update': (can_be_edited & is_speaker) | orga_can_change_submissions,
            'delete': orga_can_change_submissions,
            'state_change': orga_or_reviewer_can_change_submission,
            'accept_or_reject': orga_or_reviewer_can_change_submission,
            'withdraw': can_be_withdrawn & is_speaker,
            'reject': can_be_rejected & orga_or_reviewer_can_change_submission,
            'accept': can_be_accepted & orga_or_reviewer_can_change_submission,
            'confirm': can_be_confirmed & (is_speaker | orga_can_change_submissions),
            'cancel': can_be_canceled & orga_can_change_submissions,
            'remove': can_be_removed & orga_can_change_submissions,
            'view_feedback_page': event_uses_feedback & is_agenda_submission_visible,
            'view_feedback': is_speaker | has_reviewer_access | orga_can_change_submissions,
            'give_feedback': is_agenda_submission_visible & is_feedback_ready,
            'is_speaker': is_speaker,
            'add_speaker': can_be_edited & can_request_speakers,
        }

    class urls(EventUrls):
        user_base = '{self.event.urls.user_submissions}{self.code}/'
        withdraw = '{user_base}withdraw'
        discard = '{user_base}discard'
        confirm = '{user_base}confirm'
        public_base = '{self.event.urls.base}talk/{self.code}'
        public = '{public_base}/'
        feedback = '{public}feedback/'
        social_image = '{public}og-image'
        ical = '{public_base}.ics'
        image = '{self.image_url}'
        invite = '{user_base}invite'
        accept_invitation = '{self.event.urls.base}invitation/{self.code}/{self.invitation_token}'
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
        delete_speaker = '{speakers}delete'
        reviews = '{base}reviews/'
        feedback = '{base}feedback/'
        toggle_featured = '{base}toggle_featured'
        apply_pending = '{base}apply_pending'
        anonymise = '{base}anonymise/'
        comments = '{base}comments/'
        quick_schedule = '{self.event.orga_urls.schedule}quick/{self.code}/'
        history = '{base}history/'

    @property
    def image_url(self):
        return self.image.url if self.image else ''

    @cached_property
    def cfp_open(self):
        deadline = self.submission_type.deadline or self.event.cfp.deadline
        return (not deadline) or now() <= deadline

    @cached_property
    def editable(self):
        if self.state == SubmissionStates.SUBMITTED:
            return self.cfp_open or (
                self.event.active_review_phase and self.event.active_review_phase.speakers_can_change_submissions
            )
        if self.state == SubmissionStates.DRAFT:
            return self.cfp_open
        return self.state in SubmissionStates.accepted_states

    @property
    def anonymised(self):
        try:
            result = json.loads(self.anonymised_data)
        except Exception:
            result = None
        if not result or not isinstance(result, dict):
            return {}
        return result

    @property
    def is_anonymised(self) -> bool:
        if self.anonymised:
            return bool(self.anonymised.get('_anonymised', False))
        return False

    @property
    def reviewer_answers(self):
        return self.answers.filter(question__is_visible_to_reviewers=True).order_by('question__position')

    @property
    def public_answers(self):
        from eventyay.base.models import TalkQuestionTarget

        qs = (
            self.answers.filter(
                Q(question__submission_types__in=[self.submission_type]) | Q(question__submission_types__isnull=True),
                question__is_public=True,
                question__event=self.event,
                question__target=TalkQuestionTarget.SUBMISSION,
            )
            .select_related('talkquestion')
            .order_by('question__position')
        )
        if self.track:
            qs = qs.filter(Q(question__tracks__in=[self.track]) | Q(question__tracks__isnull=True))
        return []

    def get_duration(self) -> int:
        """Returns this submission's duration in minutes.

        Falls back to the
        :class:`~pretalx.submission.models.type.SubmissionType`'s default
        duration if none is set on the submission.
        """
        if self.duration is None:
            return self.submission_type.default_duration
        return self.duration

    def get_tag(self):
        tags = []
        for tag in self.tags.all():
            tags.append({'id': tag.id, 'tag': tag.tag, 'color': tag.color})
        return tags

    def update_duration(self):
        """Apply the submission's duration to its currently scheduled.

        :class:`~pretalx.schedule.models.slot.TalkSlot`.

        Should be called whenever the duration changes.
        """
        for slot in self.event.wip_schedule.talks.filter(submission=self, start__isnull=False):
            slot.end = slot.start + dt.timedelta(minutes=self.get_duration())
            slot.save()

    update_duration.alters_data = True

    def save(self, *args, **kwargs):
        is_creating = not self.pk
        super().save(*args, **kwargs)
        if is_creating and not self.state == SubmissionStates.DRAFT:
            submission_state_change.send_robust(
                self.event,
                submission=self,
                old_state=None,
                user=None,
            )

    def update_review_scores(self):
        """Apply the submission's calculated review scores.

        Should be called whenever the tracks of a submission change.
        """
        for review in self.reviews.all():
            review.save(update_score=True)

    def _set_state(self, new_state, force=False, person=None):
        """Check if the new state is valid for this Submission (based on
        SubmissionStates.valid_next_states).

        If yes, set it and save the object. if no, raise a
        SubmissionError with a helpful message.
        """
        valid_next_states = SubmissionStates.valid_next_states.get(self.state, [])

        if self.state == new_state:
            self.pending_state = None
            self.save(update_fields=['state', 'pending_state'])
            self.update_talk_slots()
            return
        if force or new_state in valid_next_states:
            old_state = self.state
            self.state = new_state
            self.pending_state = None
            if new_state in (
                SubmissionStates.REJECTED,
                SubmissionStates.DELETED,
                SubmissionStates.CANCELED,
                SubmissionStates.WITHDRAWN,
            ):
                self.is_featured = False
            self.save(update_fields=['state', 'pending_state'])
            self.update_talk_slots()
            submission_state_change.send_robust(
                self.event,
                submission=self,
                old_state=old_state if old_state != SubmissionStates.DRAFT else None,
                user=person,
            )
        else:
            source_states = (src for src, dsts in SubmissionStates.valid_next_states.items() if new_state in dsts)

            # build an error message mentioning all states, which are valid source states for the desired new state.
            trans_or = pgettext_lazy(
                'used in talk confirm/accept/reject/...-errors, like "... must be accepted OR foo OR bar ..."',
                ' or ',
            )
            state_names = dict(SubmissionStates.get_choices())
            source_states = trans_or.join(str(state_names[state]) for state in source_states)
            raise SubmissionError(
                _('Proposal must be {src_states} not {state} to be {new_state}.').format(
                    src_states=source_states, state=self.state, new_state=new_state
                )
            )

    def update_talk_slots(self):
        """Makes sure the correct amount of.

        :class:`~pretalx.schedule.models.slot.TalkSlot` objects exists.

        After an update or state change, talk slots should either be all
        deleted, or all created, or the number of talk slots might need
        to be adjusted.
        """
        from eventyay.base.models import TalkSlot

        scheduling_allowed = (
            self.state in SubmissionStates.accepted_states or self.pending_state in SubmissionStates.accepted_states
        )

        if not scheduling_allowed:
            TalkSlot.objects.filter(submission=self, schedule=self.event.wip_schedule).delete()
            return

        slot_count_current = TalkSlot.objects.filter(
            submission=self,
            schedule=self.event.wip_schedule,
        ).count()
        diff = slot_count_current - self.slot_count

        if diff > 0:
            # We build a list of all IDs to delete as .delete() doesn't work on sliced querysets.
            # We delete unscheduled talks first.
            talks_to_delete = (
                TalkSlot.objects.filter(
                    submission=self,
                    schedule=self.event.wip_schedule,
                )
                .order_by('start', 'room', 'is_visible')[:diff]
                .values_list('id', flat=True)
            )
            TalkSlot.objects.filter(pk__in=list(talks_to_delete)).delete()
        elif diff < 0:
            for __ in repeat(None, abs(diff)):
                TalkSlot.objects.create(
                    submission=self,
                    schedule=self.event.wip_schedule,
                )
        TalkSlot.objects.filter(submission=self, schedule=self.event.wip_schedule).update(
            is_visible=self.state == SubmissionStates.CONFIRMED
        )

    update_talk_slots.alters_data = True

    def send_initial_mails(self, person):
        from .mail import MailTemplateRoles

        template = self.event.get_mail_template(MailTemplateRoles.NEW_SUBMISSION)
        template_text = copy.deepcopy(template.text)
        locale = self.get_email_locale(person.locale)
        with override(locale):
            if '{full_submission_content}' not in str(template.text):
                template.text = (
                    str(template.text)
                    + '\n\n\n***********\n\n'
                    + str(_('Full proposal content:\n\n') + '{full_submission_content}')
                )
        template.to_mail(
            user=person,
            event=self.event,
            context_kwargs={
                'user': person,
                'submission': self,
            },
            context={
                'full_submission_content': self.get_content_for_mail(),
            },
            skip_queue=True,
            commit=True,  # Send immediately, but save a record
            locale=self.get_email_locale(person.locale),
        )
        template.refresh_from_db()
        if template.text != template_text:
            template.text = template_text
            template.save()
        if self.event.mail_settings['mail_on_new_submission']:
            self.event.get_mail_template(MailTemplateRoles.NEW_SUBMISSION_INTERNAL).to_mail(
                user=self.event.email,
                event=self.event,
                context_kwargs={
                    'user': person,
                    'submission': self,
                },
                context={'orga_url': self.orga_urls.base.full()},
                skip_queue=True,
                commit=False,  # Send immediately, don't save a record
                locale=self.event.locale,
            )

    def make_submitted(
        self,
        person=None,
        force: bool = False,
        orga: bool = False,
        from_pending: bool = False,
    ):
        """Sets the submission's state to 'submitted'."""
        previous = self.state
        self._set_state(SubmissionStates.SUBMITTED, force, person=person)
        if previous == SubmissionStates.DRAFT and person:
            self.send_initial_mails(person=person)
        else:
            self.log_action(
                'pretalx.submission.make_submitted',
                person=person,
                orga=orga,
                data={'previous': previous, 'from_pending': from_pending},
            )

    make_submitted.alters_data = True

    def confirm(
        self,
        person=None,
        force: bool = False,
        orga: bool = False,
        from_pending: bool = False,
    ):
        """Sets the submission's state to 'confirmed'."""
        previous = self.state
        self._set_state(SubmissionStates.CONFIRMED, force, person=person)
        self.log_action(
            'pretalx.submission.confirm',
            person=person,
            orga=orga,
            data={'previous': previous, 'from_pending': from_pending},
        )

    confirm.alters_data = True

    def accept(
        self,
        person=None,
        force: bool = False,
        orga: bool = True,
        from_pending: bool = False,
    ):
        """Sets the submission's state to 'accepted'.

        Creates an acceptance :class:`~pretalx.mail.models.QueuedMail`
        unless the submission was previously confirmed.
        """
        previous = self.state
        self._set_state(SubmissionStates.ACCEPTED, force, person=person)
        self.log_action(
            'pretalx.submission.accept',
            person=person,
            orga=True,
            data={'previous': previous, 'from_pending': from_pending},
        )

        if previous not in (SubmissionStates.ACCEPTED, SubmissionStates.CONFIRMED):
            self.send_state_mail()

    accept.alters_data = True

    def reject(
        self,
        person=None,
        force: bool = False,
        orga: bool = True,
        from_pending: bool = False,
    ):
        """Sets the submission's state to 'rejected' and creates a rejection.

        :class:`~pretalx.mail.models.QueuedMail`.
        """
        previous = self.state
        self._set_state(SubmissionStates.REJECTED, force, person=person)
        self.log_action(
            'pretalx.submission.reject',
            person=person,
            orga=True,
            data={'previous': previous, 'from_pending': from_pending},
        )

        if previous != SubmissionStates.REJECTED:
            self.send_state_mail()

    reject.alters_data = True

    def apply_pending_state(self, person=None, force: bool = False):
        if not self.pending_state:
            return

        if self.pending_state == self.state:
            self.pending_state = None
            self.save()
            return

        getattr(self, SubmissionStates.method_names[self.pending_state])(force=force, person=person, from_pending=True)

    apply_pending_state.alters_data = True

    def get_email_locale(self, fallback=None):
        if self.content_locale in self.event.locales:
            return self.content_locale
        if fallback and fallback in self.event.locales:
            return fallback
        return self.event.locale

    def get_content_locale_display(self):
        return str(dict(self.event.named_content_locales)[self.content_locale])

    def send_state_mail(self):
        from .mail import MailTemplateRoles

        if self.state == SubmissionStates.ACCEPTED:
            template = self.event.get_mail_template(MailTemplateRoles.SUBMISSION_ACCEPT)
        elif self.state == SubmissionStates.REJECTED:
            template = self.event.get_mail_template(MailTemplateRoles.SUBMISSION_REJECT)
        else:
            return

        for speaker in self.speakers.all():
            template.to_mail(
                user=speaker,
                locale=self.get_email_locale(speaker.locale),
                context_kwargs={'submission': self, 'user': speaker},
                event=self.event,
            )

    send_state_mail.alters_data = True

    def cancel(
        self,
        person=None,
        force: bool = False,
        orga: bool = True,
        from_pending: bool = False,
    ):
        """Sets the submission's state to 'canceled'."""
        previous = self.state
        self._set_state(SubmissionStates.CANCELED, force, person=person)
        self.log_action(
            'pretalx.submission.cancel',
            person=person,
            orga=True,
            data={'previous': previous, 'from_pending': from_pending},
        )

    cancel.alters_data = True

    def withdraw(
        self,
        person=None,
        force: bool = False,
        orga: bool = False,
        from_pending: bool = False,
    ):
        """Sets the submission's state to 'withdrawn'."""
        previous = self.state
        self._set_state(SubmissionStates.WITHDRAWN, force, person=person)
        self.log_action(
            'pretalx.submission.withdraw',
            person=person,
            orga=orga,
            data={'previous': previous, 'from_pending': from_pending},
        )

    withdraw.alters_data = True

    def remove(
        self,
        person=None,
        force: bool = False,
        orga: bool = True,
        from_pending: bool = False,
    ):
        """Sets the submission's state to 'deleted'."""
        previous = self.state
        self._set_state(SubmissionStates.DELETED, force, person=person)
        for answer in self.answers.all():
            answer.remove(person=person, force=force)
        self.log_action(
            'pretalx.submission.deleted',
            person=person,
            orga=True,
            data={'previous': previous, 'from_pending': from_pending},
        )

    remove.alters_data = True

    def delete(self, force: bool = False, **kwargs):
        if self.state != SubmissionStates.DRAFT and not force:
            raise SubmissionError(
                'Submission is not in draft mode and cannot be deleted completely. Set the deleted flag instead.'
            )
        self.answers.all().delete()
        self.resources.all().delete()
        super().delete(**kwargs)

    @cached_property
    def integer_uuid(self):
        # For import into Engelsystem, we need to somehow convert our submission code into an unique integer. Luckily,
        # codes can contain 34 different characters (including compatibility with frab imported data) and normally have
        # 6 charactes. Since log2(34 **6) == 30.52, that just fits in to a positive 32-bit signed integer (that
        # Engelsystem expects), if we do it correctly.
        charset = self._code_charset + [
            '1',
            '2',
            '4',
            '5',
            '6',
            '0',
        ]  # compatibility with imported frab data
        base = len(charset)
        table = {char: cp for cp, char in enumerate(charset)}

        intval = 0
        for char in self.code:
            intval *= base
            intval += table[char]
        return intval

    @cached_property
    def slot(self):
        """The first scheduled :class:`~pretalx.schedule.models.slot.TalkSlot`
        of this submission in the current.

        :class:`~pretalx.schedule.models.schedule.Schedule`.

        Note that this slot is not guaranteed to be visible.
        """
        return (
            self.event.current_schedule.talks.filter(submission=self)
            .select_related('room', 'submission', 'submission__event')
            .first()
            if self.event.current_schedule
            else None
        )

    @cached_property
    def current_slots(self):
        if not self.event.current_schedule:
            return None
        return self.event.current_schedule.talks.filter(submission=self, is_visible=True).select_related('room')

    @cached_property
    def public_slots(self):
        """All publicly visible :class:`~pretalx.schedule.models.slot.TalkSlot`
        objects of this submission in the current.

        :class:`~pretalx.schedule.models.schedule.Schedule`.
        """
        if not is_agenda_visible(None, self.event):
            return []
        return self.current_slots

    @cached_property
    def display_speaker_names(self):
        """Helper method for a consistent speaker name display."""
        return ', '.join(speaker.get_display_name() for speaker in self.speakers.all())

    @cached_property
    def display_title_with_speakers(self):
        title = f'{phrases.base.quotation_open}{self.title}{phrases.base.quotation_close}'
        if not self.speakers.exists():
            return title
        return _('{title_in_quotes} by {list_of_speakers}').format(
            title_in_quotes=title,
            list_of_speakers=self.display_speaker_names,
        )

    @cached_property
    def does_accept_feedback(self):
        slot = self.slot
        if slot and slot.start:
            return slot.start < now()
        return False

    @cached_property
    def median_score(self) -> float | None:
        scores = [review.score for review in self.reviews.all() if review.score is not None]
        return statistics.median(scores) if scores else None

    @cached_property
    def mean_score(self) -> float | None:
        scores = [review.score for review in self.reviews.all() if review.score is not None]
        return round(statistics.fmean(scores), 1) if scores else None

    @cached_property
    def score_categories(self):
        track = self.track
        track_filter = models.Q(limit_tracks__isnull=True)
        if track:
            track_filter |= models.Q(limit_tracks__in=[track])
        return self.event.score_categories.filter(track_filter, active=True).order_by('id')

    @cached_property
    def active_resources(self):
        return self.resources.filter(
            models.Q(  # either the resource exists
                ~models.Q(resource='') & models.Q(resource__isnull=False) & ~models.Q(resource='None')
            )
            | models.Q(models.Q(link__isnull=False) & ~models.Q(link=''))  # or the link exists
        ).order_by('link')

    @property
    def is_deleted(self):
        return self.state == SubmissionStates.DELETED

    @property
    def user_state(self):
        if self.state == SubmissionStates.SUBMITTED and not self.cfp_open:
            return 'review'
        return self.state

    def __str__(self):
        """Help when debugging."""
        return f'Submission(event={self.event.slug}, code={self.code}, title={self.title}, state={self.state})'

    @cached_property
    def export_duration(self):
        return serialize_duration(minutes=self.get_duration())

    @cached_property
    def speaker_profiles(self):
        from .profile import SpeakerProfile

        return SpeakerProfile.objects.filter(event=self.event, user__in=self.speakers.all())

    @property
    def availabilities(self):
        """The intersection of all.

        :class:`~pretalx.schedule.models.availability.Availability` objects of
        all speakers of this submission.
        """
        from .availability import Availability

        all_availabilities = self.event.availabilities.filter(person__in=self.speaker_profiles)
        return Availability.intersection(all_availabilities)

    def get_content_for_mail(self):
        order = [
            'title',
            'abstract',
            'description',
            'notes',
            'duration',
            'content_locale',
            'do_not_record',
            'image',
        ]
        data = []
        result = ''
        for field in order:
            field_content = getattr(self, field, None)
            if field_content:
                _field = self._meta.get_field(field)
                field_name = _field.verbose_name or _field.name
                data.append({'name': field_name, 'value': field_content})
        for answer in self.answers.all().order_by('question__position'):
            if answer.talkquestion.variant == 'boolean':
                data.append({'name': answer.talkquestion.question, 'value': answer.boolean_answer})
            elif answer.answer_file:
                data.append({'name': answer.talkquestion.question, 'value': answer.answer_file})
            else:
                data.append({'name': answer.talkquestion.question, 'value': answer.answer or '-'})
        for content in data:
            field_name = content['name']
            field_content = content['value']
            if isinstance(field_content, bool):
                field_content = _('Yes') if field_content else _('No')
            elif isinstance(field_content, FieldFile):
                field_content = (self.event.custom_domain or settings.SITE_URL) + field_content.url
            result += f'**{field_name}**: {field_content}\n\n'
        return result

    def add_speaker(self, email, name=None, locale=None, user=None):
        from eventyay.common.urls import build_absolute_uri

        from .auth import User
        from .mail import MailTemplateRoles
        from .profile import SpeakerProfile
        from eventyay.person.services import create_user

        user_created = False
        context = {}
        try:
            speaker = User.objects.get(email__iexact=email)
            if not speaker.profiles.filter(event=self.event).exists():
                SpeakerProfile.objects.create(user=speaker, event=self.event)
        except User.DoesNotExist:
            speaker = User.objects.create_user(email=email, name=name, event=self.event)
            user_created = True
            context['invitation_link'] = build_absolute_uri(
                'cfp:event.new_recover',
                kwargs={'event': self.event.slug, 'token': speaker.pw_reset_token},
            )

        self.speakers.add(speaker)
        self.log_action('pretalx.submission.speakers.add', person=user, orga=True)
        context['user'] = speaker
        template = self.event.get_mail_template(
            MailTemplateRoles.EXISTING_SPEAKER_INVITE if not user_created else MailTemplateRoles.NEW_SPEAKER_INVITE
        )
        template.to_mail(
            user=speaker,
            event=self.event,
            context=context,
            context_kwargs={'user': speaker, 'submission': self, 'event': self.event},
            locale=locale or self.event.locale,
        )
        return speaker

    def remove_speaker(self, speaker, orga=True, user=None):
        if self.speakers.filter(code=speaker.code).exists():
            self.speakers.remove(speaker)
            self.log_action(
                'pretalx.submission.speakers.remove',
                person=user or speaker,
                orga=orga,
                data={
                    'code': speaker.code,
                    'email': speaker.email,
                    'name': speaker.name,
                },
            )

    def send_invite(self, to, _from=None, subject=None, text=None):
        from .mail import QueuedMail

        if not _from and (not subject or not text):
            raise ValueError('Please enter a sender for this invitation.')

        subject = subject or phrases.cfp.invite_subject.format(speaker=_from.get_display_name())
        text = text or phrases.cfp.invite_text.format(
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
                locale=self.get_email_locale(),
            ).send()

    send_invite.alters_data = True

    def add_favourite(self, user):
        SubmissionFavourite.objects.get_or_create(user=user, submission=self)

    def remove_favourite(self, user):
        SubmissionFavourite.objects.filter(user=user, submission=self).delete()


class SubmissionFavouriteDeprecated(models.Model):
    user = models.OneToOneField(
        to='User',
        related_name='submission_favorites',
        on_delete=models.PROTECT,
        verbose_name=_n('User', 'Users', 1),
    )
    talk_list = JSONField(null=True, blank=True, verbose_name=_('List favourite talk'))

    class Meta:
        db_table = '"submission_submission_favourites"'


class SubmissionFavouriteDeprecatedSerializer(serializers.ModelSerializer):
    user = serializers.SlugRelatedField(slug_field='id', read_only=True)

    def __init__(self, user_id=None, **kwargs):
        super().__init__(**kwargs)
        self.user = user_id

    class Meta:
        model = SubmissionFavouriteDeprecated
        fields = ['user', 'talk_list']

    def save(self, user_id, talk_code):
        with scopes_disabled():
            user = get_object_or_404(User, id=user_id)
            submission_fav, _created = SubmissionFavouriteDeprecated.objects.get_or_create(user=user)
            submission_fav.talk_list = talk_code
            submission_fav.save()
            return submission_fav


class SubmissionFavourite(PretalxModel):
    user = models.ForeignKey(
        to='User',
        on_delete=models.CASCADE,
        related_name='submission_favourites',
    )
    submission = models.ForeignKey(
        to='Submission',
        on_delete=models.CASCADE,
        related_name='favourites',
    )
    objects = ScopedManager(event='submission__event')

    class Meta:
        unique_together = (('user', 'submission'),)
