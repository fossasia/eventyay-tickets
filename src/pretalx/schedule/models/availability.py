import datetime
from typing import List

from django.db import models

from pretalx.common.mixins import LogMixin


class Availability(LogMixin, models.Model):
    event = models.ForeignKey(
        to='event.Event',
        related_name='availabilities',
        on_delete=models.CASCADE,
    )
    person = models.ForeignKey(
        to='person.SpeakerProfile',
        related_name='availabilities',
        on_delete=models.CASCADE,
        null=True, blank=True,
    )
    room = models.ForeignKey(
        to='schedule.Room',
        related_name='availabilities',
        on_delete=models.CASCADE,
        null=True, blank=True,
    )
    start = models.DateTimeField()
    end = models.DateTimeField()

    def __str__(self) -> str:
        person = getattr(self.person, 'nick', None)
        room = getattr(self.room, 'name', None)
        return f'Availability(event={self.event.slug}, person={person}, room={room})'

    def __eq__(self, other: 'Availability') -> bool:
        if not isinstance(other, Availability):
            return False
        return all([
            getattr(self, attribute, None) == getattr(other, attribute, None)
            for attribute in ['event', 'person', 'room', 'start', 'end']
        ])

    def serialize(self) -> dict:
        zerotime = datetime.time(0, 0)
        return {
            'id': self.id,
            'start': str(self.start),
            'end': str(self.end),
            # make sure all-day availabilities are displayed properly in fullcalendar
            'allDay': (self.start.time() == zerotime and self.end.time() == zerotime)
        }

    def overlaps(self, other: 'Availability', strict: bool) -> bool:
        """ Test if two Availabilities overlap. Includes direct adjacency, if in strict mode """

        if not isinstance(other, Availability):
            raise Exception('Please provide an Availability object')

        if strict:
            return (self.start <= other.start < self.end) or \
                   (self.start < other.end <= self.end) or \
                   (other.start <= self.start < other.end) or \
                   (other.start < self.end <= other.end)
        else:
            return (self.start <= other.start <= self.end) or \
                   (self.start <= other.end <= self.end) or \
                   (other.start <= self.start <= other.end) or \
                   (other.start <= self.end <= other.end)

    def merge_with(self, other: 'Availability') -> 'Availability':
        """ Return a new Availability which spans the range of this one and the given one """

        if not isinstance(other, Availability):
            raise Exception('Please provide an Availability object.')
        if not other.overlaps(self, strict=False):
            raise Exception('Only overlapping Availabilities can be merged.')

        return Availability(
            start=min(self.start, other.start),
            end=max(self.end, other.end),
        )

    def __or__(self, other: 'Availability') -> 'Availability':
        return self.merge_with(other)

    def intersect_with(self, other: 'Availability') -> 'Availability':
        """ Return a new Availability which spans the range covered both by this one and the given one """

        if not isinstance(other, Availability):
            raise Exception('Please provide an Availability object.')
        if not other.overlaps(self, False):
            raise Exception('Only overlapping Availabilities can be intersected.')

        return Availability(
            start=max(self.start, other.start),
            end=min(self.end, other.end),
        )

    def __and__(self, other: 'Availability') -> 'Availability':
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
    def _pair_intersection(cls, availabilities_a: List['Availability'], availabilities_b: List['Availability']) -> List['Availability']:
        """ return the list of Availabilities, which are covered by each of the given sets """
        if not availabilities_a or not availabilities_b:
            return []

        result = []

        # yay for O(b*a) time! I am sure there is some fancy trick to make this faster,
        # but we're dealing with less than 100 items in total, sooo.. ¯\_(ツ)_/¯
        for a in availabilities_a:
            for b in availabilities_b:
                if a.overlaps(b, True):
                    result.append(a.intersect_with(b))

        return result

    @classmethod
    def intersection(cls, *availabilitysets: List['Availability']) -> List['Availability']:
        """ Return the list of Availabilities which are covered by all of the given sets """

        # get rid of any overlaps and unmerged ranges in each set
        availabilitysets = [
            cls.union(avialset)
            for avialset in availabilitysets
        ]

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
