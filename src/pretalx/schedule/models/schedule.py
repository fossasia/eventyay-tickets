from collections import defaultdict
from contextlib import suppress
from urllib.parse import quote

import pytz
from django.conf import settings
from django.db import models, transaction
from django.template.loader import get_template
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.timezone import override as tzoverride
from django.utils.translation import gettext_lazy as _
from django.utils.translation import override
from django_scopes import ScopedManager
from i18nfield.fields import I18nTextField

from pretalx.agenda.tasks import export_schedule_html
from pretalx.common.mixins import LogMixin
from pretalx.common.phrases import phrases
from pretalx.common.urls import EventUrls
from pretalx.mail.context import template_context_from_event
from pretalx.person.models import User
from pretalx.submission.models import SubmissionStates


class Schedule(LogMixin, models.Model):
    """The Schedule model contains all scheduled.

    :class:`~pretalx.schedule.models.slot.TalkSlot` objects (visible or not)
    for a schedule release for an :class:`~pretalx.event.models.event.Event`.

    :param published: ``None`` if the schedule has not been published yet.
    """

    event = models.ForeignKey(
        to="event.Event", on_delete=models.PROTECT, related_name="schedules"
    )
    version = models.CharField(
        max_length=190, null=True, blank=True, verbose_name=_("version")
    )
    published = models.DateTimeField(null=True, blank=True)
    comment = I18nTextField(
        null=True,
        blank=True,
        help_text=_("This text will be shown in the public changelog and the RSS feed.")
        + " "
        + phrases.base.use_markdown,
    )

    objects = ScopedManager(event="event")

    class Meta:
        ordering = ("-published",)
        unique_together = (("event", "version"),)

    class urls(EventUrls):
        public = "{self.event.urls.schedule}v/{self.url_version}/"

    @transaction.atomic
    def freeze(
        self, name: str, user=None, notify_speakers: bool = True, comment: str = None
    ):
        """Releases the current WIP schedule as a fixed schedule version.

        :param name: The new schedule name. May not be in use in this event,
            and cannot be 'wip' or 'latest'.
        :param user: The :class:`~pretalx.person.models.user.User` initiating
            the freeze.
        :param notify_speakers: Should notification emails for speakers with
            changed slots be generated?
        :param comment: Public comment for the release
        :rtype: Schedule
        """
        from pretalx.schedule.models import TalkSlot

        if name in ["wip", "latest"]:
            raise Exception(f'Cannot use reserved name "{name}" for schedule version.')
        if self.version:
            raise Exception(
                f'Cannot freeze schedule version: already versioned as "{self.version}".'
            )
        if not name:
            raise Exception("Cannot create schedule version without a version name.")

        self.version = name
        self.comment = comment
        self.published = now()
        self.save(update_fields=["published", "version", "comment"])
        self.log_action("pretalx.schedule.release", person=user, orga=True)

        wip_schedule = Schedule.objects.create(event=self.event)

        # Set visibility
        self.talks.all().update(is_visible=False)
        self.talks.filter(
            models.Q(submission__state=SubmissionStates.CONFIRMED)
            | models.Q(submission__isnull=True),
            start__isnull=False,
        ).update(is_visible=True)

        talks = []
        for talk in self.talks.select_related("submission", "room").all():
            talks.append(talk.copy_to_schedule(wip_schedule, save=False))
        TalkSlot.objects.bulk_create(talks)

        if notify_speakers:
            self.generate_notifications(save=True)

        with suppress(AttributeError):
            del wip_schedule.event.wip_schedule
        with suppress(AttributeError):
            del wip_schedule.event.current_schedule

        if self.event.settings.export_html_on_schedule_release:
            if settings.HAS_CELERY:
                export_schedule_html.apply_async(kwargs={"event_id": self.event.id})
            else:
                self.event.cache.set("rebuild_schedule_export", True, None)
        return self, wip_schedule

    freeze.alters_data = True

    @transaction.atomic
    def unfreeze(self, user=None):
        """Resets the current WIP schedule to an older schedule version."""
        from pretalx.schedule.models import TalkSlot

        if not self.version:
            raise Exception("Cannot unfreeze schedule version: not released yet.")

        # collect all talks, which have been added since this schedule (#72)
        submission_ids = self.talks.all().values_list("submission_id", flat=True)
        talks = self.event.wip_schedule.talks.exclude(
            submission_id__in=submission_ids
        ).union(self.talks.all())

        wip_schedule = Schedule.objects.create(event=self.event)
        new_talks = []
        for talk in talks:
            new_talks.append(talk.copy_to_schedule(wip_schedule, save=False))
        TalkSlot.objects.bulk_create(new_talks)

        self.event.wip_schedule.talks.all().delete()
        self.event.wip_schedule.delete()

        with suppress(AttributeError):
            del wip_schedule.event.wip_schedule

        return self, wip_schedule

    unfreeze.alters_data = True

    @cached_property
    def scheduled_talks(self):
        """Returns all :class:`~pretalx.schedule.models.slot.TalkSlot` objects
        that have been scheduled."""
        return (
            self.talks.select_related("submission", "submission__event", "room",)
            .filter(
                room__isnull=False,
                start__isnull=False,
                is_visible=True,
                submission__isnull=False,
            )
            .exclude(submission__state=SubmissionStates.DELETED)
        )

    @cached_property
    def breaks(self):
        return self.talks.select_related("room").filter(submission__isnull=True)

    @cached_property
    def slots(self):
        """Returns all.

        :class:`~pretalx.submission.models.submission.Submission` objects with
        :class:`~pretalx.schedule.models.slot.TalkSlot` objects in this
        schedule.
        """
        from pretalx.submission.models import Submission

        return Submission.objects.filter(
            id__in=self.scheduled_talks.values_list("submission", flat=True)
        )

    @cached_property
    def previous_schedule(self):
        """Returns the schedule released before this one, if any."""
        queryset = self.event.schedules.exclude(pk=self.pk)
        if self.published:
            queryset = queryset.filter(published__lt=self.published)
        return queryset.order_by("-published").first()

    def _handle_submission_move(self, submission_pk, old_slots, new_slots):
        new = []
        canceled = []
        moved = []
        all_old_slots = list(old_slots.filter(submission__pk=submission_pk))
        all_new_slots = list(new_slots.filter(submission__pk=submission_pk))
        old_slots = [
            slot
            for slot in all_old_slots
            if not any(slot.is_same_slot(other_slot) for other_slot in all_new_slots)
        ]
        new_slots = [
            slot
            for slot in all_new_slots
            if not any(slot.is_same_slot(other_slot) for other_slot in all_old_slots)
        ]
        diff = len(old_slots) - len(new_slots)
        if diff > 0:
            canceled = old_slots[:diff]
            old_slots = old_slots[diff:]
        elif diff < 0:
            diff = -diff
            new = new_slots[:diff]
            new_slots = new_slots[diff:]
        for move in zip(old_slots, new_slots):
            old_slot = move[0]
            new_slot = move[1]
            moved.append(
                {
                    "submission": new_slot.submission,
                    "old_start": old_slot.start.astimezone(self.tz),
                    "new_start": new_slot.start.astimezone(self.tz),
                    "old_room": old_slot.room.name,
                    "new_room": new_slot.room.name,
                    "new_info": new_slot.room.speaker_info,
                }
            )
        return new, canceled, moved

    @cached_property
    def tz(self):
        return pytz.timezone(self.event.timezone)

    @cached_property
    def changes(self) -> dict:
        """Returns a dictionary of changes when compared to the previous
        version.

        The ``action`` field is either ``create`` or ``update``. If it's
        an update, the ``count`` integer, and the ``new_talks``,
        ``canceled_talks`` and ``moved_talks`` lists are also present.
        """
        result = {
            "count": 0,
            "action": "update",
            "new_talks": [],
            "canceled_talks": [],
            "moved_talks": [],
        }
        if not self.previous_schedule:
            result["action"] = "create"
            return result

        old_slots = self.previous_schedule.scheduled_talks
        new_slots = self.scheduled_talks
        old_slot_set = set(
            old_slots.values_list("submission", "room", "start", named=True)
        )
        new_slot_set = set(
            new_slots.values_list("submission", "room", "start", named=True)
        )
        old_submissions = set(old_slots.values_list("submission__id", flat=True))
        new_submissions = set(new_slots.values_list("submission__id", flat=True))
        handled_submissions = set()

        moved_or_missing = old_slot_set - new_slot_set - {None}
        moved_or_new = new_slot_set - old_slot_set - {None}

        for entry in moved_or_missing:
            if entry.submission in handled_submissions or not entry.submission:
                continue
            if entry.submission not in new_submissions:
                result["canceled_talks"] += list(
                    old_slots.filter(submission__pk=entry.submission)
                )
            else:
                new, canceled, moved = self._handle_submission_move(
                    entry.submission, old_slots, new_slots
                )
                result["new_talks"] += new
                result["canceled_talks"] += canceled
                result["moved_talks"] += moved
            handled_submissions.add(entry.submission)
        for entry in moved_or_new:
            if entry.submission in handled_submissions:
                continue
            if entry.submission not in old_submissions:
                result["new_talks"] += list(
                    new_slots.filter(submission__pk=entry.submission)
                )
            else:
                new, canceled, moved = self._handle_submission_move(
                    entry.submission, old_slots, new_slots
                )
                result["new_talks"] += new
                result["canceled_talks"] += canceled
                result["moved_talks"] += moved
            handled_submissions.add(entry.submission)

        result["count"] = (
            len(result["new_talks"])
            + len(result["canceled_talks"])
            + len(result["moved_talks"])
        )
        return result

    @cached_property
    def warnings(self) -> dict:
        """A dictionary of warnings to be acknowledged before a release.

        ``talk_warnings`` contains a list of talk-related warnings.
        ``unscheduled`` is the list of talks without a scheduled slot,
        ``unconfirmed`` is the list of submissions that will not be
        visible due to their unconfirmed status, and ``no_track`` are
        submissions without a track in a conference that uses tracks.
        """
        warnings = {
            "talk_warnings": [],
            "unscheduled": [],
            "unconfirmed": [],
            "no_track": [],
        }
        for talk in self.talks.filter(submission__isnull=False):
            if not talk.start:
                warnings["unscheduled"].append(talk)
            elif talk.warnings:
                warnings["talk_warnings"].append(talk)
            if talk.submission.state != SubmissionStates.CONFIRMED:
                warnings["unconfirmed"].append(talk)
            if talk.submission.event.settings.use_tracks and not talk.submission.track:
                warnings["no_track"].append(talk)
        return warnings

    @cached_property
    def speakers_concerned(self):
        """Returns a dictionary of speakers with their new and changed talks in
        this schedule.

        Each speaker is assigned a dictionary with ``create`` and
        ``update`` fields, each containing a list of submissions.
        """
        if self.changes["action"] == "create":
            result = {}
            for speaker in User.objects.filter(submissions__slots__schedule=self):
                talks = self.talks.filter(
                    submission__speakers=speaker,
                    room__isnull=False,
                    start__isnull=False,
                )
                if talks:
                    result[speaker] = {"create": talks, "update": []}
            return result

        if self.changes["count"] == len(self.changes["canceled_talks"]):
            return []

        speakers = defaultdict(lambda: {"create": [], "update": []})
        for new_talk in self.changes["new_talks"]:
            for speaker in new_talk.submission.speakers.all():
                speakers[speaker]["create"].append(new_talk)
        for moved_talk in self.changes["moved_talks"]:
            for speaker in moved_talk["submission"].speakers.all():
                speakers[speaker]["update"].append(moved_talk)
        return speakers

    def generate_notifications(self, save=False):
        """A list of unsaved :class:`~pretalx.mail.models.QueuedMail` objects
        to be sent on schedule release."""
        mails = []
        for speaker in self.speakers_concerned:
            with override(speaker.locale), tzoverride(self.tz):
                notifications = get_template(
                    "schedule/speaker_notification.txt"
                ).render({"speaker": speaker, **self.speakers_concerned[speaker]})
            context = template_context_from_event(self.event)
            context["notifications"] = notifications
            mails.append(
                self.event.update_template.to_mail(
                    user=speaker, event=self.event, context=context, commit=save
                )
            )
        return mails

    generate_notifications.alters_data = True

    @cached_property
    def url_version(self):
        return quote(self.version) if self.version else "wip"

    @cached_property
    def is_archived(self):
        if not self.version:
            return False

        return self != self.event.current_schedule

    def __str__(self) -> str:
        """Help when debugging."""
        return f"Schedule(event={self.event.slug}, version={self.version})"
