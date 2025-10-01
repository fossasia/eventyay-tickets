import string

from django.db import models
from django.db.models import Q
from django.utils.crypto import get_random_string
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy as _p

from eventyay.api.versions import CURRENT_VERSIONS
from .mixins import PretalxModel


def generate_api_token():
    return get_random_string(length=64, allowed_chars=string.ascii_lowercase + string.digits)


READ_PERMISSIONS = ('list', 'retrieve')
WRITE_PERMISSIONS = READ_PERMISSIONS + ('create', 'update', 'destroy', 'actions')
PERMISSION_CHOICES = (
    ('list', _p('Read list', 'API endpoint permissions')),
    ('retrieve', _p('Read details', 'API endpoint permissions')),
    ('create', _p('Create', 'API endpoint permissions')),
    ('update', _p('Update', 'API endpoint permissions')),
    ('destroy', _p('Delete', 'API endpoint permissions')),
    ('actions', _p('Additional actions', 'API endpoint permissions')),
)
ENDPOINTS = (
    'teams',
    'events',
    'submissions',
    'speakers',
    'reviews',
    'rooms',
    'questions',
    'question-options',
    'answers',
    'tags',
    'tracks',
    'schedules',
    'slots',
    'submission-types',
    'mail-templates',
    'access-codes',
    'speaker-information',
)


class UserApiTokenManager(models.Manager):
    def active(self):
        return self.get_queryset().filter(Q(expires__isnull=True) | Q(expires__gt=now()))


class UserApiToken(PretalxModel):
    name = models.CharField(max_length=190, verbose_name=_('Name'))
    token = models.CharField(default=generate_api_token, max_length=64, unique=True)
    user = models.ForeignKey(
        to='User',
        related_name='api_tokens',
        on_delete=models.CASCADE,
    )
    events = models.ManyToManyField(
        to='Event',
        related_name='+',
        verbose_name=_('Events'),
    )
    expires = models.DateTimeField(null=True, blank=True, verbose_name=_('Expiry date'))
    endpoints = models.JSONField(default=dict, blank=True)
    version = models.CharField(max_length=12, null=True, blank=True, verbose_name=_('API version'))
    last_used = models.DateTimeField(null=True, blank=True)

    objects = UserApiTokenManager()

    def has_endpoint_permission(self, endpoint, method):
        if method == 'partial_update':
            # We don't track separate permissions for partial updates
            method = 'update'
        elif method not in dict(PERMISSION_CHOICES):
            method = 'actions'
        return method in self.endpoints.get(endpoint, [])

    @property
    def is_active(self):
        return not self.expires or self.expires > now()

    @property
    def is_latest_version(self):
        return not self.version or self.version in CURRENT_VERSIONS

    def serialize(self):
        return {
            'name': self.name,
            'token': self.token,
            'events': [e.slug for e in self.events.all()],
            'expires': self.expires.isoformat() if self.expires else None,
            'endpoints': self.endpoints,
            'version': self.version,
        }

    def update_events(self):
        """Called when a user loses access to a team. Should remove any events the user
        does not have access anymore from this token’s events."""
        user_permitted_events = set(self.user.get_events_with_any_permission())
        token_current_events = set(self.events.all())

        events_to_remove = token_current_events - user_permitted_events
        if events_to_remove:
            for event in events_to_remove:
                self.events.remove(event)
            if not self.events.all():
                self.expires = now()
                self.save()
