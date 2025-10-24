from django.core.exceptions import ValidationError
from django.db import models
from django.utils.crypto import get_random_string
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_scopes import ScopedManager

from pretix.base.models import LoggedModel


class Room(LoggedModel):
    """
    A room represents a physical or virtual space within an event where
    attendees can check in and check out independently from the main event.
    This enables tracking attendance for parallel sessions, workshops, or tracks.
    """
    
    event = models.ForeignKey(
        'Event',
        related_name='rooms',
        on_delete=models.CASCADE,
        verbose_name=_('Event')
    )
    name = models.CharField(
        max_length=200,
        verbose_name=_('Room name'),
        help_text=_('The display name of the room')
    )
    identifier = models.CharField(
        max_length=50,
        verbose_name=_('Room identifier'),
        help_text=_('A unique identifier for the room within the event')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Description'),
        help_text=_('Optional description of the room')
    )
    location = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_('Location'),
        help_text=_('Physical location or address of the room')
    )
    capacity = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Capacity'),
        help_text=_('Maximum number of attendees allowed in the room')
    )
    session_start = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Session start time'),
        help_text=_('When the session in this room starts')
    )
    session_end = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Session end time'),
        help_text=_('When the session in this room ends')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active'),
        help_text=_('Whether check-ins are currently allowed for this room')
    )
    gates = models.ManyToManyField(
        'pretixbase.Gate',
        related_name='rooms',
        blank=True,
        verbose_name=_('Gates'),
        help_text=_('Gates associated with this room for session check-ins')
    )
    
    objects = ScopedManager(organizer='event__organizer')
    
    class Meta:
        unique_together = [('event', 'identifier')]
        ordering = ['name']
        verbose_name = _('Room')
        verbose_name_plural = _('Rooms')
    
    def __str__(self):
        return f"{self.name} ({self.identifier})"
    
    def clean(self):
        super().clean()
        if self.session_start and self.session_end and self.session_start >= self.session_end:
            raise ValidationError(_('Session start time must be before session end time.'))
    
    @property
    def current_occupancy(self):
        """Returns the current number of people checked into this room."""
        return self.checkins.filter(
            type=RoomCheckin.TYPE_ENTRY
        ).exclude(
            position__in=self.checkins.filter(
                type=RoomCheckin.TYPE_EXIT,
                datetime__gt=models.F('datetime')
            ).values_list('position_id', flat=True)
        ).count()
    
    @property
    def is_at_capacity(self):
        """Returns True if the room is at or over capacity."""
        if not self.capacity:
            return False
        return self.current_occupancy >= self.capacity


class RoomCheckin(models.Model):
    """
    A room check-in object is created when a person enters or exits a specific room.
    This is separate from the main event check-in system and allows for independent
    tracking of room attendance.
    """
    
    TYPE_ENTRY = 'entry'
    TYPE_EXIT = 'exit'
    CHECKIN_TYPES = (
        (TYPE_ENTRY, _('Entry')),
        (TYPE_EXIT, _('Exit')),
    )
    
    room = models.ForeignKey(
        'Room',
        related_name='checkins',
        on_delete=models.CASCADE,
        verbose_name=_('Room')
    )
    position = models.ForeignKey(
        'pretixbase.OrderPosition',
        related_name='room_checkins',
        on_delete=models.CASCADE,
        verbose_name=_('Order position')
    )
    datetime = models.DateTimeField(
        default=now,
        verbose_name=_('Check-in time')
    )
    type = models.CharField(
        max_length=10,
        choices=CHECKIN_TYPES,
        default=TYPE_ENTRY,
        verbose_name=_('Type')
    )
    device = models.ForeignKey(
        'pretixbase.Device',
        related_name='room_checkins',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_('Device')
    )
    gate = models.ForeignKey(
        'pretixbase.Gate',
        related_name='room_checkins',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Gate')
    )
    nonce = models.CharField(
        max_length=190,
        null=True,
        blank=True,
        verbose_name=_('Nonce')
    )
    forced = models.BooleanField(
        default=False,
        verbose_name=_('Forced')
    )
    # Pseudonymization fields for privacy
    pseudonymization_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        verbose_name=_('Pseudonymization ID'),
        help_text=_('Anonymized identifier for privacy compliance')
    )
    
    objects = ScopedManager(organizer='room__event__organizer')
    
    class Meta:
        ordering = ['-datetime']
        verbose_name = _('Room check-in')
        verbose_name_plural = _('Room check-ins')
    
    def __str__(self):
        return f"{self.get_type_display()} - {self.room.name} at {self.datetime}"
    
    def save(self, **kwargs):
        # Generate pseudonymization ID if not provided
        if not self.pseudonymization_id:
            self.pseudonymization_id = get_random_string(
                length=32,
                allowed_chars='abcdefghijklmnopqrstuvwxyz0123456789'
            )
        super().save(**kwargs)
        # Touch related objects for cache invalidation
        self.position.order.touch()
    
    @property
    def duration_in_room(self):
        """Calculate how long the person stayed in the room (if they've exited)."""
        if self.type != self.TYPE_EXIT:
            return None
        
        # Find the most recent entry for this position in this room
        last_entry = RoomCheckin.objects.filter(
            room=self.room,
            position=self.position,
            type=self.TYPE_ENTRY,
            datetime__lt=self.datetime
        ).order_by('-datetime').first()
        
        if last_entry:
            return self.datetime - last_entry.datetime
        return None