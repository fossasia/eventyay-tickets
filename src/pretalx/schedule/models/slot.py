import datetime as dt
import re
import string
import uuid
from contextlib import suppress
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import vobject
from django.conf import settings
from django.db import models
from django.utils.functional import cached_property
from django_scopes import ScopedManager
from i18nfield.fields import I18nCharField

from pretalx.common.mixins.models import PretalxModel
from pretalx.common.urls import get_base_url

INSTANCE_IDENTIFIER = None
with suppress(Exception):
    from pretalx.common.models.settings import GlobalSettings

    INSTANCE_IDENTIFIER = GlobalSettings().get_instance_identifier()


class TalkSlot(PretalxModel):
    """The TalkSlot object is the scheduled version of a.

    :class:`~pretalx.submission.models.submission.Submission`.

    TalkSlots always belong to one submission and one :class:`~pretalx.schedule.models.schedule.Schedule`.

    :param is_visible: This parameter is set on schedule release. Only confirmed talks will be visible.
    """

    submission = models.ForeignKey(
        to="submission.Submission",
        on_delete=models.PROTECT,
        related_name="slots",
        null=True,
        blank=True,  # If the submission is empty, this is a break or similar event
    )
    room = models.ForeignKey(
        to="schedule.Room",
        on_delete=models.PROTECT,
        related_name="talks",
        null=True,
        blank=True,
    )
    schedule = models.ForeignKey(
        to="schedule.Schedule", on_delete=models.PROTECT, related_name="talks"
    )
    is_visible = models.BooleanField(default=False)
    start = models.DateTimeField(null=True)
    end = models.DateTimeField(null=True)
    description = I18nCharField(null=True)

    objects = ScopedManager(event="schedule__event")

    class Meta:
        ordering = ("start",)

    def __str__(self):
        """Help when debugging."""
        return f'TalkSlot(event={self.schedule.event.slug}, submission={getattr(self.submission, "title", None)}, schedule={self.schedule.version})'

    @cached_property
    def event(self):
        return self.submission.event if self.submission else self.schedule.event

    @property
    def duration(self) -> int:
        """Returns the actual duration in minutes if the talk is scheduled, and
        the planned duration in minutes otherwise."""
        if self.start and self.end:
            return int((self.end - self.start).total_seconds() / 60)
        if not self.submission:
            return None
        return self.submission.get_duration()

    @cached_property
    def export_duration(self):
        from pretalx.common.serialize import serialize_duration

        return serialize_duration(minutes=self.duration)

    @cached_property
    def pentabarf_export_duration(self):
        duration = dt.timedelta(minutes=self.duration)
        days = duration.days
        hours = duration.total_seconds() // 3600 - days * 24
        minutes = duration.seconds // 60 % 60
        return f"{hours:02}{minutes:02}00"

    @cached_property
    def local_start(self):
        if self.start:
            return self.start.astimezone(self.event.tz)

    @cached_property
    def real_end(self):
        """Guaranteed to provide a useful end datetime if ``start`` is set,
        even if ``end`` is empty."""
        return self.end or (
            self.start + dt.timedelta(minutes=self.duration) if self.start else None
        )

    @cached_property
    def local_end(self):
        if self.real_end:
            return self.real_end.astimezone(self.event.tz)

    @cached_property
    def as_availability(self):
        """'Casts' a slot as.

        :class:`~pretalx.schedule.models.availability.Availability`, useful for
        availability arithmetic.
        """
        from pretalx.schedule.models import Availability

        return Availability(
            start=self.start,
            end=self.real_end,
        )

    def copy_to_schedule(self, new_schedule, save=True):
        """Create a new slot for the given.

        :class:`~pretalx.schedule.models.schedule.Schedule` with all other
        fields identical to this one.
        """
        new_slot = TalkSlot(schedule=new_schedule)

        for field in [f for f in self._meta.fields if f.name not in ("id", "schedule")]:
            setattr(new_slot, field.name, getattr(self, field.name))

        if save:
            new_slot.save()
        return new_slot

    copy_to_schedule.alters_data = True

    def is_same_slot(self, other_slot) -> bool:
        """Checks if both slots have the same room and start time."""
        return self.room == other_slot.room and self.start == other_slot.start

    @cached_property
    def id_suffix(self):
        if not self.event.feature_flags["present_multiple_times"]:
            return ""
        all_slots = list(
            TalkSlot.objects.filter(
                submission_id=self.submission_id, schedule_id=self.schedule_id
            )
        )
        if len(all_slots) == 1:
            return ""
        return "-" + str(all_slots.index(self))

    @cached_property
    def frab_slug(self):
        title = re.sub(r"\W+", "-", self.submission.title)
        legal_chars = string.ascii_letters + string.digits + "-"
        pattern = f"[^{legal_chars}]+"
        title = re.sub(pattern, "", title)
        title = title.lower()
        title = title.strip("_")
        return f"{self.event.slug}-{self.submission.pk}{self.id_suffix}-{title}"

    @cached_property
    def uuid(self):
        """A UUID5, calculated from the submission code and the instance
        identifier."""
        global INSTANCE_IDENTIFIER
        if not INSTANCE_IDENTIFIER:
            from pretalx.common.models.settings import GlobalSettings

            INSTANCE_IDENTIFIER = GlobalSettings().get_instance_identifier()
        return uuid.uuid5(INSTANCE_IDENTIFIER, self.submission.code + self.id_suffix)

    def build_ical(self, calendar, creation_time=None, netloc=None):
        if not self.start or not self.local_end or not self.room or not self.submission:
            return
        creation_time = creation_time or dt.datetime.now(ZoneInfo("UTC"))
        netloc = netloc or urlparse(get_base_url(self.event)).netloc

        vevent = calendar.add("vevent")
        vevent.add("summary").value = (
            f"{self.submission.title} - {self.submission.display_speaker_names}"
        )
        vevent.add("dtstamp").value = creation_time
        vevent.add("location").value = str(self.room.name)
        vevent.add("uid").value = "pretalx-{}-{}{}@{}".format(
            self.submission.event.slug, self.submission.code, self.id_suffix, netloc
        )

        vevent.add("dtstart").value = self.local_start
        vevent.add("dtend").value = self.local_end
        vevent.add("description").value = self.submission.abstract or ""
        vevent.add("url").value = self.submission.urls.public.full()

    def full_ical(self):
        netloc = urlparse(settings.SITE_URL).netloc
        cal = vobject.iCalendar()
        cal.add("prodid").value = "-//pretalx//{}//{}".format(
            netloc, self.submission.code
        )
        self.build_ical(cal)
        return cal
