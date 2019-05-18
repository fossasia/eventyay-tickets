import datetime
from typing import List

from django.db import models
from django.utils.functional import cached_property
from django_scopes import ScopedManager

from pretalx.common.mixins import LogMixin

zerotime = datetime.time(0, 0)


class Availability(LogMixin, models.Model):
    """The Availability class models when people or rooms are available for :class:`~pretalx.schedule.models.slot.TalkSlot` objects.

    The power of this class is not within its rather simple data model, but
    with the operations available on it. An availability object can span
    multiple days, but due to our choice of input widget, it will usually
    only span a single day at most.
    """
    event = models.ForeignKey(
        to='event.Event', related_name='availabilities', on_delete=models.CASCADE
    )
    person = models.ForeignKey(
        to='person.SpeakerProfile',
        related_name='availabilities',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    room = models.ForeignKey(
        to='schedule.Room',
        related_name='availabilities',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    start = models.DateTimeField()
    end = models.DateTimeField()

    objects = ScopedManager(event='event')

    def __str__(self) -> str:
        person = self.person.user.get_display_name() if self.person else None
        room = getattr(self.room, 'name', None)
        event = getattr(getattr(self, 'event', None), 'slug', None)
        return f'Availability(event={event}, person={person}, room={room})'

    def __hash__(self):
        return hash((self.event, self.person, self.room, self.start, self.end))

    def __eq__(self, other: 'Availability') -> bool:
        """Comparisons like ``availability1 == availability2``.

        Checks if ``event``, ``person``, ``room``, ``start`` and ``end`` are
        the same.
        """
        return all(
            [
                getattr(self, attribute, None) == getattr(other, attribute, None)
                for attribute in ['event', 'person', 'room', 'start', 'end']
            ]
        )

    @cached_property
    def all_day(self) -> bool:
        """Checks if the Availability spans one (or, technically: multiple) complete day."""
        return self.start.time() == zerotime and self.end.time() == zerotime

    def serialize(self) -> dict:
        from pretalx.api.serializers.room import AvailabilitySerializer

        return AvailabilitySerializer(self).data

    def overlaps(self, other: 'Availability', strict: bool) -> bool:
        """Test if two Availabilities overlap.

        :param strict: Count direct adjacency as overlap.
        """

        if not isinstance(other, Availability):
            raise Exception('Please provide an Availability object')

        if strict:
            return (
                (self.start <= other.start < self.end)
                or (self.start < other.end <= self.end)
                or (other.start <= self.start < other.end)
                or (other.start < self.end <= other.end)
            )
        return (
            (self.start <= other.start <= self.end)
            or (self.start <= other.end <= self.end)
            or (other.start <= self.start <= other.end)
            or (other.start <= self.end <= other.end)
        )

    def contains(self, other: 'Availability') -> bool:
        """Tests if this availability starts before and ends after the other."""
        return self.start <= other.start and self.end >= other.end

    def merge_with(self, other: 'Availability') -> 'Availability':
        """Return a new Availability which spans the range of this one and the given one."""

        if not isinstance(other, Availability):
            raise Exception('Please provide an Availability object.')
        if not other.overlaps(self, strict=False):
            raise Exception('Only overlapping Availabilities can be merged.')

        return Availability(
            start=min(self.start, other.start), end=max(self.end, other.end)
        )

    def __or__(self, other: 'Availability') -> 'Availability':
        """Performs the merge operation: ``availability1 | availability2``"""
        return self.merge_with(other)

    def intersect_with(self, other: 'Availability') -> 'Availability':
        """Return a new Availability which spans the range covered both by this one and the given one."""

        if not isinstance(other, Availability):
            raise Exception('Please provide an Availability object.')
        if not other.overlaps(self, False):
            raise Exception('Only overlapping Availabilities can be intersected.')

        return Availability(
            start=max(self.start, other.start), end=min(self.end, other.end)
        )

    def __and__(self, other: 'Availability') -> 'Availability':
        """Performs the intersect operation: ``availability1 & availability2``"""
        return self.intersect_with(other)

    @classmethod
    def union(cls, availabilities: List['Availability']) -> List['Availability']:
        """ Return the minimal list of Availability objects which are covered by at least one given Availability """
        if not availabilities:
            return []

        availabilities = sorted(availabilities, key=lambda a: a.start)
        result = [availabilities[0]]
        availabilities = availabilities[1:]

        for avail in availabilities:
            if avail.overlaps(result[-1], False):
                result[-1] = result[-1].merge_with(avail)
            else:
                result.append(avail)

        return result

    @classmethod
    def _pair_intersection(
        cls,
        availabilities_a: List['Availability'],
        availabilities_b: List['Availability'],
    ) -> List['Availability']:
        """ return the list of Availabilities, which are covered by each of the given sets """
        result = []

        # yay for O(b*a) time! I am sure there is some fancy trick to make this faster,
        # but we're dealing with less than 100 items in total, sooo.. ¯\_(ツ)_/¯
        for a in availabilities_a:
            for b in availabilities_b:
                if a.overlaps(b, True):
                    result.append(a.intersect_with(b))

        return result

    @classmethod
    def intersection(
        cls, *availabilitysets: List['Availability']
    ) -> List['Availability']:
        """ Return the list of Availabilities which are covered by all of the given sets """

        # get rid of any overlaps and unmerged ranges in each set
        availabilitysets = [cls.union(avialset) for avialset in availabilitysets]
        # bail out for obvious cases (there are no sets given, one of the sets is empty)
        if not availabilitysets:
            return []
        if not all(availabilitysets):
            return []
        # start with the very first set ...
        result = availabilitysets[0]
        for availset in availabilitysets[1:]:
            # ... subtract each of the other sets
            result = cls._pair_intersection(result, availset)
        return result
