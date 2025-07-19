import string
import uuid
from collections import OrderedDict
from datetime import datetime, time, timedelta
from operator import attrgetter
from typing import List
from urllib.parse import urljoin

import pytz
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.mail import get_connection
from django.core.validators import (
    MaxValueValidator,
    MinLengthValidator,
    MinValueValidator,
    RegexValidator,
)
from django.db import models
from django.db.models import Exists, OuterRef, Prefetch, Q, Subquery, Value
from django.template.defaultfilters import date as _date
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.formats import date_format
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.timezone import make_aware, now
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django_scopes import ScopedManager, scopes_disabled
from i18nfield.fields import I18nCharField, I18nTextField

from eventyay.base.models.base import LoggedModel
from eventyay.base.models.fields import MultiStringField
from eventyay.base.reldate import RelativeDateWrapper
from eventyay.base.settings import GlobalSettingsObject
from eventyay.base.validators import EventSlugBanlistValidator
from eventyay.helpers.database import GroupConcat
from eventyay.helpers.daterange import daterange
from eventyay.helpers.json import safe_string
from eventyay.helpers.thumb import get_thumbnail

from ..settings import settings_hierarkey
from .organizer import Organizer, OrganizerBillingModel, Team

TALK_HOSTNAME = settings.TALK_HOSTNAME

# Import permissions for the default functions
from eventyay.core.permissions import Permission, SYSTEM_ROLES
from eventyay.core.utils.json import CustomJSONEncoder


def default_roles():
    attendee = [
        Permission.EVENT_VIEW,
        Permission.EVENT_EXHIBITION_CONTACT,
        Permission.EVENT_CHAT_DIRECT,
    ]
    viewer = attendee + [Permission.ROOM_VIEW, Permission.ROOM_CHAT_READ]
    participant = viewer + [
        Permission.ROOM_CHAT_JOIN,
        Permission.ROOM_CHAT_SEND,
        Permission.ROOM_QUESTION_READ,
        Permission.ROOM_QUESTION_ASK,
        Permission.ROOM_QUESTION_VOTE,
        Permission.ROOM_POLL_READ,
        Permission.ROOM_POLL_VOTE,
        Permission.ROOM_ROULETTE_JOIN,
        Permission.ROOM_BBB_JOIN,
        Permission.ROOM_JANUSCALL_JOIN,
        Permission.ROOM_ZOOM_JOIN,
    ]
    room_creator = [Permission.EVENT_ROOMS_CREATE_CHAT]
    room_owner = participant + [
        Permission.ROOM_INVITE,
        Permission.ROOM_DELETE,
    ]
    speaker = participant + [
        Permission.ROOM_BBB_MODERATE,
        Permission.ROOM_JANUSCALL_MODERATE,
        Permission.ROOM_POLL_EARLY_RESULTS,
    ]
    moderator = speaker + [
        Permission.ROOM_VIEWERS,
        Permission.ROOM_CHAT_MODERATE,
        Permission.ROOM_ANNOUNCE,
        Permission.ROOM_BBB_RECORDINGS,
        Permission.ROOM_QUESTION_MODERATE,
        Permission.ROOM_POLL_EARLY_RESULTS,
        Permission.ROOM_POLL_MANAGE,
        Permission.EVENT_ANNOUNCE,
    ]
    admin = (
        moderator
        + room_creator
        + [
            Permission.EVENT_UPDATE,
            Permission.ROOM_DELETE,
            Permission.ROOM_UPDATE,
            Permission.EVENT_ROOMS_CREATE_BBB,
            Permission.EVENT_ROOMS_CREATE_STAGE,
            Permission.EVENT_ROOMS_CREATE_EXHIBITION,
            Permission.EVENT_ROOMS_CREATE_POSTER,
            Permission.EVENT_USERS_LIST,
            Permission.EVENT_USERS_MANAGE,
            Permission.EVENT_GRAPHS,
            Permission.EVENT_CONNECTIONS_UNLIMITED,
        ]
    )
    apiuser = admin + [Permission.EVENT_API, Permission.EVENT_SECRETS]
    scheduleuser = [Permission.EVENT_API]
    return {
        "attendee": attendee,
        "viewer": viewer,
        "participant": participant,
        "room_creator": room_creator,
        "room_owner": room_owner,
        "speaker": speaker,
        "moderator": moderator,
        "admin": admin,
        "apiuser": apiuser,
        "scheduleuser": scheduleuser,
    }


def default_grants():
    return {
        "attendee": ["attendee"],
        "admin": ["admin"],
        "scheduleuser": ["schedule-update"],
    }


FEATURE_FLAGS = [
    "schedule-control",
    "iframe-player",
    "roulette",
    "muxdata",
    "page.landing",
    "zoom",
    "janus",
    "polls",
    "poster",
    "conftool",
    "cross-origin-isolation",
]


def default_feature_flags():
    return ["chat-moderation"]


class EventMixin:
    def clean(self):
        if self.presale_start and self.presale_end and self.presale_start > self.presale_end:
            raise ValidationError({'presale_end': _('The end of the presale period has to be later than its start.')})
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValidationError({'date_to': _('The end of the event has to be later than its start.')})
        super().clean()

    def get_short_date_from_display(self, tz=None, show_times=True) -> str:
        """
        Returns a shorter formatted string containing the start date of the event with respect
        to the current locale and to the ``show_times`` setting.
        """
        tz = tz or self.timezone
        return _date(
            self.date_from.astimezone(tz),
            ('SHORT_DATETIME_FORMAT' if self.settings.show_times and show_times else 'DATE_FORMAT'),
        )

    def get_short_date_to_display(self, tz=None) -> str:
        """
        Returns a shorter formatted string containing the start date of the event with respect
        to the current locale and to the ``show_times`` setting. Returns an empty string
        if ``show_date_to`` is ``False``.
        """
        tz = tz or self.timezone
        if not self.settings.show_date_to or not self.date_to:
            return ''
        return _date(
            self.date_to.astimezone(tz),
            'SHORT_DATETIME_FORMAT' if self.settings.show_times else 'DATE_FORMAT',
        )

    def get_date_from_display(self, tz=None, show_times=True, short=False) -> str:
        """
        Returns a formatted string containing the start date of the event with respect
        to the current locale and to the ``show_times`` setting.
        """
        tz = tz or self.timezone
        return _date(
            self.date_from.astimezone(tz),
            ('SHORT_' if short else '')
            + ('DATETIME_FORMAT' if self.settings.show_times and show_times else 'DATE_FORMAT'),
        )

    def get_time_from_display(self, tz=None) -> str:
        """
        Returns a formatted string containing the start time of the event, ignoring
        the ``show_times`` setting.
        """
        tz = tz or self.timezone
        return _date(self.date_from.astimezone(tz), 'TIME_FORMAT')

    def get_date_to_display(self, tz=None, show_times=True, short=False) -> str:
        """
        Returns a formatted string containing the start date of the event with respect
        to the current locale and to the ``show_times`` setting. Returns an empty string
        if ``show_date_to`` is ``False``.
        """
        tz = tz or self.timezone
        if not self.settings.show_date_to or not self.date_to:
            return ''
        return _date(
            self.date_to.astimezone(tz),
            ('SHORT_' if short else '')
            + ('DATETIME_FORMAT' if self.settings.show_times and show_times else 'DATE_FORMAT'),
        )

    def get_date_range_display(self, tz=None, force_show_end=False) -> str:
        """
        Returns a formatted string containing the start date and the end date
        of the event with respect to the current locale and to the ``show_date_to``
        setting. Times are not shown.
        """
        tz = tz or self.timezone
        if (not self.settings.show_date_to and not force_show_end) or not self.date_to:
            return _date(self.date_from.astimezone(tz), 'DATE_FORMAT')
        return daterange(self.date_from.astimezone(tz), self.date_to.astimezone(tz))

    @property
    def timezone(self):
        return pytz.timezone(self.settings.timezone)

    @property
    def effective_presale_end(self):
        """
        Returns the effective presale end date, taking for subevents into consideration if the presale end
        date might have been further limited by the event-level presale end date
        """
        if isinstance(self, SubEvent):
            presale_ends = [self.presale_end, self.event.presale_end]
            return min(filter(lambda x: x is not None, presale_ends)) if any(presale_ends) else None
        else:
            return self.presale_end

    @property
    def presale_has_ended(self):
        """
        Is true, when ``presale_end`` is set and in the past.
        """
        if self.effective_presale_end:
            return now() > self.effective_presale_end
        elif self.date_to:
            return now() > self.date_to
        else:
            return now().astimezone(self.timezone).date() > self.date_from.astimezone(self.timezone).date()

    @property
    def effective_presale_start(self):
        """
        Returns the effective presale start date, taking for subevents into consideration if the presale start
        date might have been further limited by the event-level presale start date
        """
        if isinstance(self, SubEvent):
            presale_starts = [self.presale_start, self.event.presale_start]
            return max(filter(lambda x: x is not None, presale_starts)) if any(presale_starts) else None
        else:
            return self.presale_start

    @property
    def presale_is_running(self):
        """
        Is true, when ``presale_end`` is not set or in the future and ``presale_start`` is not
        set or in the past.
        """
        if self.effective_presale_start and now() < self.effective_presale_start:
            return False
        return not self.presale_has_ended

    @property
    def event_microdata(self):
        import json

        eventdict = {
            '@context': 'http://schema.org',
            '@type': 'Event',
            'location': {
                '@type': 'Place',
                'address': str(self.location),
            },
            'name': str(self.name),
        }
        img = getattr(self, 'event', self).social_image
        if img:
            eventdict['image'] = img

        if self.settings.show_times:
            eventdict['startDate'] = self.date_from.isoformat()
            if self.settings.show_date_to and self.date_to is not None:
                eventdict['endDate'] = self.date_to.isoformat()
        else:
            eventdict['startDate'] = self.date_from.date().isoformat()
            if self.settings.show_date_to and self.date_to is not None:
                eventdict['endDate'] = self.date_to.date().isoformat()

        return safe_string(json.dumps(eventdict))

    @classmethod
    def annotated(cls, qs, channel='web'):
        from eventyay.base.models import Item, ItemVariation, Quota

        sq_active_item = (
            Item.objects.using(settings.DATABASE_REPLICA)
            .filter_available(channel=channel)
            .filter(Q(variations__isnull=True) & Q(quotas__pk=OuterRef('pk')))
            .order_by()
            .values_list('quotas__pk')
            .annotate(items=GroupConcat('pk', delimiter=','))
            .values('items')
        )
        sq_active_variation = (
            ItemVariation.objects.filter(
                Q(active=True)
                & Q(item__active=True)
                & Q(Q(item__available_from__isnull=True) | Q(item__available_from__lte=now()))
                & Q(Q(item__available_until__isnull=True) | Q(item__available_until__gte=now()))
                & Q(Q(item__category__isnull=True) | Q(item__category__is_addon=False))
                & Q(item__sales_channels__contains=channel)
                & Q(item__hide_without_voucher=False)
                & Q(item__require_bundling=False)
                & Q(quotas__pk=OuterRef('pk'))
            )
            .order_by()
            .values_list('quotas__pk')
            .annotate(items=GroupConcat('pk', delimiter=','))
            .values('items')
        )
        return qs.annotate(
            has_paid_item=Exists(Item.objects.filter(event_id=OuterRef(cls._event_id), default_price__gt=0))
        ).prefetch_related(
            Prefetch(
                'quotas',
                to_attr='active_quotas',
                queryset=Quota.objects.using(settings.DATABASE_REPLICA)
                .annotate(
                    active_items=Subquery(sq_active_item, output_field=models.TextField()),
                    active_variations=Subquery(sq_active_variation, output_field=models.TextField()),
                )
                .exclude(Q(active_items='') & Q(active_variations=''))
                .select_related('event', 'subevent'),
            )
        )

    @cached_property
    def best_availability_state(self):
        from .items import Quota

        if not hasattr(self, 'active_quotas'):
            raise TypeError('Call this only if you fetched the subevents via Event/SubEvent.annotated()')
        items_available = set()
        vars_available = set()
        items_reserved = set()
        vars_reserved = set()
        items_gone = set()
        vars_gone = set()

        r = getattr(self, '_quota_cache', {})
        for q in self.active_quotas:
            res = r[q] if q in r else q.availability(allow_cache=True)

            if res[0] == Quota.AVAILABILITY_OK:
                if q.active_items:
                    items_available.update(q.active_items.split(','))
                if q.active_variations:
                    vars_available.update(q.active_variations.split(','))
            elif res[0] == Quota.AVAILABILITY_RESERVED:
                if q.active_items:
                    items_reserved.update(q.active_items.split(','))
                if q.active_variations:
                    vars_available.update(q.active_variations.split(','))
            elif res[0] < Quota.AVAILABILITY_RESERVED:
                if q.active_items:
                    items_gone.update(q.active_items.split(','))
                if q.active_variations:
                    vars_gone.update(q.active_variations.split(','))
        if not self.active_quotas:
            return None
        if items_available - items_reserved - items_gone or vars_available - vars_reserved - vars_gone:
            return Quota.AVAILABILITY_OK
        if items_reserved - items_gone or vars_reserved - vars_gone:
            return Quota.AVAILABILITY_RESERVED
        return Quota.AVAILABILITY_GONE

    def free_seats(self, ignore_voucher=None, sales_channel='web', include_blocked=False):
        qs_annotated = self._seats(ignore_voucher=ignore_voucher)

        qs = qs_annotated.filter(has_order=False, has_cart=False, has_voucher=False)
        if self.settings.seating_minimal_distance > 0:
            qs = qs.filter(has_closeby_taken=False)

        if not (sales_channel in self.settings.seating_allow_blocked_seats_for_channel or include_blocked):
            qs = qs.filter(blocked=False)
        return qs

    def total_seats(self, ignore_voucher=None):
        return self._seats(ignore_voucher=ignore_voucher)

    def taken_seats(self, ignore_voucher=None):
        return self._seats(ignore_voucher=ignore_voucher).filter(has_order=True)

    def blocked_seats(self, ignore_voucher=None):
        qs = self._seats(ignore_voucher=ignore_voucher)
        q = Q(has_cart=True) | Q(has_voucher=True) | Q(blocked=True)
        if self.settings.seating_minimal_distance > 0:
            q |= Q(has_closeby_taken=True, has_order=False)
        return qs.filter(q)


@settings_hierarkey.add(parent_field='organizer', cache_namespace='event')
class Event(EventMixin, LoggedModel):
    """
    This model represents an event. An event is anything you can buy
    tickets for.

    :param organizer: The organizer this event belongs to
    :type organizer: Organizer
    :param testmode: This event is in test mode
    :type testmode: bool
    :param name: This event's full title
    :type name: str
    :param slug: A short, alphanumeric, all-lowercase name for use in URLs. The slug has to
                 be unique among the events of the same organizer.
    :type slug: str
    :param live: Whether or not the shop is publicly accessible
    :type live: bool
    :param currency: The currency of all prices and payments of this event
    :type currency: str
    :param date_from: The datetime this event starts
    :type date_from: datetime
    :param date_to: The datetime this event ends
    :type date_to: datetime
    :param presale_start: No tickets will be sold before this date.
    :type presale_start: datetime
    :param presale_end: No tickets will be sold after this date.
    :type presale_end: datetime
    :param location: venue
    :type location: str
    :param plugins: A comma-separated list of plugin names that are active for this
                    event.
    :type plugins: str
    :param has_subevents: Enable event series functionality
    :type has_subevents: bool
    :param sales_channels: A list of sales channel identifiers, that this event is available for sale on
    :type sales_channels: list
    """

    settings_namespace = 'event'
    _event_id = 'pk'
    CURRENCY_CHOICES = [(c.alpha_3, c.alpha_3 + ' - ' + c.name) for c in settings.CURRENCIES]
    organizer = models.ForeignKey(Organizer, related_name='events', on_delete=models.PROTECT)
    testmode = models.BooleanField(default=False)
    name = I18nCharField(
        max_length=200,
        verbose_name=_('Event name'),
    )
    slug = models.CharField(
        max_length=50,
        db_index=True,
        help_text=_(
            'Should be short, only contain lowercase letters, numbers, dots, and dashes, and must be unique among your '
            'events. We recommend some kind of abbreviation or a date with less than 10 characters that can be easily '
            'remembered, but you can also choose to use a random value. '
            'This will be used in URLs, order codes, invoice numbers, and bank transfer references.'
        ),
        validators=[
            MinLengthValidator(
                limit_value=2,
            ),
            RegexValidator(
                regex='^[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9]$',
                message=_('The slug may only contain letters, numbers, dots and dashes.'),
            ),
            EventSlugBanlistValidator(),
        ],
        verbose_name=_('Short form'),
    )
    live = models.BooleanField(default=False, verbose_name=_('Shop is live'))
    currency = models.CharField(
        max_length=10,
        verbose_name=_('Event currency'),
        choices=CURRENCY_CHOICES,
        default=settings.DEFAULT_CURRENCY,
    )
    date_from = models.DateTimeField(verbose_name=_('Event start time'))
    date_to = models.DateTimeField(null=True, blank=True, verbose_name=_('Event end time'))
    date_admission = models.DateTimeField(null=True, blank=True, verbose_name=_('Admission time'))
    is_public = models.BooleanField(
        default=True,
        verbose_name=_('Show in lists'),
        help_text=_('If selected, this event will show up publicly on the list of events for your organizer account.'),
    )
    presale_end = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('End of presale'),
        help_text=_(
            'Optional. No products will be sold after this date. If you do not set this value, the presale '
            'will end after the end date of your event.'
        ),
    )
    presale_start = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Start of presale'),
        help_text=_('Optional. No products will be sold before this date.'),
    )
    location = I18nTextField(
        null=True,
        blank=True,
        max_length=200,
        verbose_name=_('Location'),
    )
    geo_lat = models.FloatField(
        verbose_name=_('Latitude'),
        null=True,
        blank=True,
        validators=[
            MinValueValidator(-90),
            MaxValueValidator(90),
        ],
    )
    geo_lon = models.FloatField(
        verbose_name=_('Longitude'),
        null=True,
        blank=True,
        validators=[
            MinValueValidator(-180),
            MaxValueValidator(180),
        ],
    )
    plugins = models.TextField(
        null=False,
        blank=True,
        verbose_name=_('Plugins'),
    )
    comment = models.TextField(verbose_name=_('Internal comment'), null=True, blank=True)
    has_subevents = models.BooleanField(verbose_name=_('Event series'), default=False)
    seating_plan = models.ForeignKey(
        'SeatingPlan',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='events',
    )
    sales_channels = MultiStringField(
        verbose_name=_('Restrict to specific sales channels'),
        help_text=_('Only sell tickets for this event on the following sales channels.'),
        default=['web'],
    )
    is_video_creation = models.BooleanField(
        verbose_name=_('Add video call'),
        help_text=_('Create Video platform for Event.'),
        default=False,
    )
    # --- Event/Room/Permissions/Config fields ---
    config = models.JSONField(null=True, blank=True)
    roles = models.JSONField(null=True, blank=True, default=default_roles, encoder=CustomJSONEncoder)
    trait_grants = models.JSONField(null=True, blank=True, default=default_grants)
    domain = models.CharField(
        max_length=250,
        unique=True,
        null=True,
        blank=True,
        validators=[RegexValidator(regex=r"^[a-z0-9-.:]+(/[a-zA-Z0-9-_./]*)?$")],
    )
    locale = models.CharField(
        max_length=100,
        default="en",
        choices=(
            ("en", "English"),
            ("de", "German"),
        ),
    )
    timezone = models.CharField(max_length=120, default="Europe/Berlin")
    feature_flags = models.JSONField(blank=True, default=default_feature_flags)
    external_auth_url = models.URLField(null=True, blank=True)

    objects = ScopedManager(organizer='organizer')

    class Meta:
        verbose_name = _('Event')
        verbose_name_plural = _('Events')
        ordering = ('date_from', 'name')
        unique_together = (('organizer', 'slug'),)

    def __str__(self):
        return str(self.name)

    def set_defaults(self):
        """
        This will be called after event creation, but only if the event was not created by copying an existing one.
        This way, we can use this to introduce new default settings to eventyay that do not affect existing events.
        """
        self.settings.invoice_renderer = 'modern1'
        self.settings.invoice_include_expire_date = True
        self.settings.ticketoutput_pdf__enabled = True
        self.settings.ticketoutput_passbook__enabled = True
        self.settings.event_list_type = 'calendar'
        self.settings.invoice_email_attachment = True
        self.settings.name_scheme = 'given_family'

    @property
    def social_image(self):
        from eventyay.multidomain.urlreverse import build_absolute_uri

        img = None
        logo_file = self.settings.get('logo_image', as_type=str, default='')[7:]
        og_file = self.settings.get('og_image', as_type=str, default='')[7:]
        if og_file:
            img = get_thumbnail(og_file, '1200').thumb.url
        elif logo_file:
            img = get_thumbnail(logo_file, '5000x120').thumb.url
        if img:
            return urljoin(build_absolute_uri(self, 'presale:event.index'), img)

    def _seats(self, ignore_voucher=None):
        from .seating import Seat

        qs_annotated = Seat.annotated(
            self.seats,
            self.pk,
            None,
            ignore_voucher_id=ignore_voucher.pk if ignore_voucher else None,
            minimal_distance=self.settings.seating_minimal_distance,
            distance_only_within_row=self.settings.seating_distance_within_row,
        )

        return qs_annotated

    @property
    def presale_has_ended(self):
        if self.has_subevents:
            return self.presale_end and now() > self.presale_end
        else:
            return super().presale_has_ended

    def delete_all_orders(self, really=False):
        from .orders import OrderFee, OrderPayment, OrderPosition, OrderRefund

        if not really:
            raise TypeError('Pass really=True as a parameter.')

        OrderPosition.all.filter(order__event=self, addon_to__isnull=False).delete()
        OrderPosition.all.filter(order__event=self).delete()
        OrderFee.objects.filter(order__event=self).delete()
        OrderRefund.objects.filter(order__event=self).delete()
        OrderPayment.objects.filter(order__event=self).delete()
        self.orders.all().delete()

    def save(self, *args, **kwargs):
        obj = super().save(*args, **kwargs)
        self.cache.clear()
        return obj

    def get_plugins(self):
        """
        Returns the names of the plugins activated for this event as a list.
        """
        if self.plugins is None:
            return []
        return self.plugins.split(',')

    def get_cache(self):
        """
        Returns an :py:class:`ObjectRelatedCache` object. This behaves equivalent to
        Django's built-in cache backends, but puts you into an isolated environment for
        this event, so you don't have to prefix your cache keys. In addition, the cache
        is being cleared every time the event or one of its related objects change.

        .. deprecated:: 1.9
           Use the property ``cache`` instead.
        """
        return self.cache

    @cached_property
    def cache(self):
        """
        Returns an :py:class:`ObjectRelatedCache` object. This behaves equivalent to
        Django's built-in cache backends, but puts you into an isolated environment for
        this event, so you don't have to prefix your cache keys. In addition, the cache
        is being cleared every time the event or one of its related objects change.
        """
        from eventyay.base.cache import ObjectRelatedCache

        return ObjectRelatedCache(self)

    def lock(self):
        """
        Returns a contextmanager that can be used to lock an event for bookings.
        """
        from eventyay.base.services import locking

        return locking.LockManager(self)

    def get_mail_backend(self, timeout=None, force_custom=False):
        """
        Returns an email server connection, either by using the system-wide connection
        or by returning a custom one based on the event's settings.
        """
        from eventyay.base.email import CustomSMTPBackend, SendGridEmail

        gs = GlobalSettingsObject()

        if self.settings.smtp_use_custom or force_custom:
            if self.settings.email_vendor == 'sendgrid':
                return SendGridEmail(api_key=self.settings.send_grid_api_key)
            return CustomSMTPBackend(
                host=self.settings.smtp_host,
                port=self.settings.smtp_port,
                username=self.settings.smtp_username,
                password=self.settings.smtp_password,
                use_tls=self.settings.smtp_use_tls,
                use_ssl=self.settings.smtp_use_ssl,
                fail_silently=False,
                timeout=timeout,
            )
        elif gs.settings.email_vendor is not None:
            if gs.settings.email_vendor == 'sendgrid':
                return SendGridEmail(api_key=gs.settings.send_grid_api_key)
            else:
                return CustomSMTPBackend(
                    host=gs.settings.smtp_host,
                    port=gs.settings.smtp_port,
                    username=gs.settings.smtp_username,
                    password=gs.settings.smtp_password,
                    use_tls=gs.settings.smtp_use_tls,
                    use_ssl=gs.settings.smtp_use_ssl,
                    fail_silently=False,
                    timeout=timeout,
                )
        else:
            return get_connection(fail_silently=False)

    @property
    def payment_term_last(self):
        """
        The last datetime of payments for this event.
        """
        tz = pytz.timezone(self.settings.timezone)
        return make_aware(
            datetime.combine(
                self.settings.get('payment_term_last', as_type=RelativeDateWrapper).datetime(self).date(),
                time(hour=23, minute=59, second=59),
            ),
            tz,
        )

    def copy_data_from(self, other):
        from ..signals import event_copy_data
        from . import (
            Item,
            ItemAddOn,
            ItemBundle,
            ItemCategory,
            ItemMetaValue,
            Question,
            Quota,
        )

        self.plugins = other.plugins
        self.is_public = other.is_public
        if other.date_admission:
            self.date_admission = self.date_from + (other.date_admission - other.date_from)
        self.testmode = other.testmode
        self.save()
        self.log_action('eventyay.object.cloned', data={'source': other.slug, 'source_id': other.pk})

        tax_map = {}
        for t in other.tax_rules.all():
            tax_map[t.pk] = t
            t.pk = None
            t.event = self
            t.save()
            t.log_action('eventyay.object.cloned')

        category_map = {}
        for c in ItemCategory.objects.filter(event=other):
            category_map[c.pk] = c
            c.pk = None
            c.event = self
            c.save()
            c.log_action('eventyay.object.cloned')

        item_meta_properties_map = {}
        for imp in other.item_meta_properties.all():
            item_meta_properties_map[imp.pk] = imp
            imp.pk = None
            imp.event = self
            imp.save()
            imp.log_action('eventyay.object.cloned')

        item_map = {}
        variation_map = {}
        for i in Item.objects.filter(event=other).prefetch_related('variations'):
            vars = list(i.variations.all())
            item_map[i.pk] = i
            i.pk = None
            i.event = self
            if i.picture:
                i.picture.save(i.picture.name, i.picture)
            if i.category_id:
                i.category = category_map[i.category_id]
            if i.tax_rule_id:
                i.tax_rule = tax_map[i.tax_rule_id]
            i.save()
            i.log_action('eventyay.object.cloned')
            for v in vars:
                variation_map[v.pk] = v
                v.pk = None
                v.item = i
                v.save()

        for imv in ItemMetaValue.objects.filter(item__event=other).prefetch_related('item', 'property'):
            imv.pk = None
            imv.property = item_meta_properties_map[imv.property.pk]
            imv.item = item_map[imv.item.pk]
            imv.save()

        for ia in ItemAddOn.objects.filter(base_item__event=other).prefetch_related('base_item', 'addon_category'):
            ia.pk = None
            ia.base_item = item_map[ia.base_item.pk]
            ia.addon_category = category_map[ia.addon_category.pk]
            ia.save()

        for ia in ItemBundle.objects.filter(base_item__event=other).prefetch_related(
            'base_item', 'bundled_item', 'bundled_variation'
        ):
            ia.pk = None
            ia.base_item = item_map[ia.base_item.pk]
            ia.bundled_item = item_map[ia.bundled_item.pk]
            if ia.bundled_variation:
                ia.bundled_variation = variation_map[ia.bundled_variation.pk]
            ia.save()

        for q in Quota.objects.filter(event=other, subevent__isnull=True).prefetch_related('items', 'variations'):
            items = list(q.items.all())
            vars = list(q.variations.all())
            oldid = q.pk
            q.pk = None
            q.event = self
            q.closed = False
            q.save()
            q.log_action('eventyay.object.cloned')
            for i in items:
                if i.pk in item_map:
                    q.items.add(item_map[i.pk])
            for v in vars:
                q.variations.add(variation_map[v.pk])
            self.items.filter(hidden_if_available_id=oldid).update(hidden_if_available=q)

        question_map = {}
        for q in Question.objects.filter(event=other).prefetch_related('items', 'options'):
            items = list(q.items.all())
            opts = list(q.options.all())
            question_map[q.pk] = q
            q.pk = None
            q.event = self
            q.save()
            q.log_action('eventyay.object.cloned')

            for i in items:
                q.items.add(item_map[i.pk])
            for o in opts:
                o.pk = None
                o.question = q
                o.save()

        for q in self.questions.filter(dependency_question__isnull=False):
            q.dependency_question = question_map[q.dependency_question_id]
            q.save(update_fields=['dependency_question'])

        def _walk_rules(rules):
            if isinstance(rules, dict):
                for k, v in rules.items():
                    if k == 'lookup':
                        if v[0] == 'product':
                            v[1] = str(item_map.get(int(v[1]), 0).pk) if int(v[1]) in item_map else '0'
                        elif v[0] == 'variation':
                            v[1] = str(variation_map.get(int(v[1]), 0).pk) if int(v[1]) in variation_map else '0'
                    else:
                        _walk_rules(v)
            elif isinstance(rules, list):
                for i in rules:
                    _walk_rules(i)

        checkin_list_map = {}
        for cl in other.checkin_lists.filter(subevent__isnull=True).prefetch_related('limit_products'):
            items = list(cl.limit_products.all())
            checkin_list_map[cl.pk] = cl
            cl.pk = None
            cl.event = self
            rules = cl.rules
            _walk_rules(rules)
            cl.rules = rules
            cl.save()
            cl.log_action('eventyay.object.cloned')
            for i in items:
                cl.limit_products.add(item_map[i.pk])

        if other.seating_plan:
            if other.seating_plan.organizer_id == self.organizer_id:
                self.seating_plan = other.seating_plan
            else:
                self.organizer.seating_plans.create(name=other.seating_plan.name, layout=other.seating_plan.layout)
            self.save()

        for m in other.seat_category_mappings.filter(subevent__isnull=True):
            m.pk = None
            m.event = self
            m.product = item_map[m.product_id]
            m.save()

        for s in other.seats.filter(subevent__isnull=True):
            s.pk = None
            s.event = self
            if s.product_id:
                s.product = item_map[s.product_id]
            s.save()

        skip_settings = (
            'ticket_secrets_eventyay_sig1_pubkey',
            'ticket_secrets_eventyay_sig1_privkey',
        )
        for s in other.settings._objects.all():
            if s.key in skip_settings:
                continue

            s.object = self
            s.pk = None
            if s.value.startswith('file://'):
                fi = default_storage.open(s.value[7:], 'rb')
                nonce = get_random_string(length=8)
                # TODO: make sure pub is always correct
                fname = 'pub/%s/%s/%s.%s.%s' % (
                    self.organizer.slug,
                    self.slug,
                    s.key,
                    nonce,
                    s.value.split('.')[-1],
                )
                newname = default_storage.save(fname, fi)
                s.value = 'file://' + newname
                s.save()
            elif s.key == 'tax_rate_default':
                try:
                    if int(s.value) in tax_map:
                        s.value = tax_map.get(int(s.value)).pk
                        s.save()
                except ValueError:
                    pass
            else:
                s.save()

        self.settings.flush()
        event_copy_data.send(
            sender=self,
            other=other,
            tax_map=tax_map,
            category_map=category_map,
            item_map=item_map,
            variation_map=variation_map,
            question_map=question_map,
            checkin_list_map=checkin_list_map,
        )

    def get_payment_providers(self, cached=False) -> dict:
        """
        Returns a dictionary of initialized payment providers mapped by their identifiers.
        """
        from ..signals import register_payment_providers

        if not cached or not hasattr(self, '_cached_payment_providers'):
            responses = register_payment_providers.send(self)
            providers = {}
            for receiver, response in responses:
                if not isinstance(response, list):
                    response = [response]
                for p in response:
                    pp = p(self)
                    providers[pp.identifier] = pp

            self._cached_payment_providers = OrderedDict(
                sorted(
                    providers.items(),
                    key=lambda v: (-v[1].priority, str(v[1].verbose_name)),
                )
            )
        return self._cached_payment_providers

    def get_html_mail_renderer(self):
        """
        Returns the currently selected HTML email renderer
        """
        return self.get_html_mail_renderers()[self.settings.mail_html_renderer]

    def get_html_mail_renderers(self) -> dict:
        """
        Returns a dictionary of initialized HTML email renderers mapped by their identifiers.
        """
        from ..signals import register_html_mail_renderers

        responses = register_html_mail_renderers.send(self)
        renderers = {}
        for receiver, response in responses:
            if not isinstance(response, list):
                response = [response]
            for p in response:
                pp = p(self)
                if pp.is_available:
                    renderers[pp.identifier] = pp
        return renderers

    def get_invoice_renderers(self) -> dict:
        """
        Returns a dictionary of initialized invoice renderers mapped by their identifiers.
        """
        from ..signals import register_invoice_renderers

        responses = register_invoice_renderers.send(self)
        renderers = {}
        for receiver, response in responses:
            if not isinstance(response, list):
                response = [response]
            for p in response:
                pp = p(self)
                renderers[pp.identifier] = pp
        return renderers

    @cached_property
    def ticket_secret_generators(self) -> dict:
        """
        Returns a dictionary of cached initialized ticket secret generators mapped by their identifiers.
        """
        from ..signals import register_ticket_secret_generators

        responses = register_ticket_secret_generators.send(self)
        renderers = {}
        for receiver, response in responses:
            if not isinstance(response, list):
                response = [response]
            for p in response:
                pp = p(self)
                renderers[pp.identifier] = pp
        return renderers

    @property
    def ticket_secret_generator(self):
        """
        Returns the currently configured ticket secret generator.
        """
        tsgs = self.ticket_secret_generators
        return tsgs.get(self.settings.ticket_secret_generator, tsgs.get('random'))

    def get_data_shredders(self) -> dict:
        """
        Returns a dictionary of initialized data shredders mapped by their identifiers.
        """
        from ..signals import register_data_shredders

        responses = register_data_shredders.send(self)
        renderers = {}
        for receiver, response in responses:
            if not isinstance(response, list):
                response = [response]
            for p in response:
                pp = p(self)
                renderers[pp.identifier] = pp
        return renderers

    @property
    def invoice_renderer(self):
        """
        Returns the currently configured invoice renderer.
        """
        irs = self.get_invoice_renderers()
        return irs[self.settings.invoice_renderer]

    def subevents_annotated(self, channel):
        return SubEvent.annotated(self.subevents, channel)

    def subevents_sorted(self, queryset):
        ordering = self.settings.get('frontpage_subevent_ordering', default='date_ascending', as_type=str)
        orderfields = {
            'date_ascending': ('date_from', 'name'),
            'date_descending': ('-date_from', 'name'),
            'name_ascending': ('name', 'date_from'),
            'name_descending': ('-name', 'date_from'),
        }[ordering]
        subevs = queryset.annotate(
            has_paid_item=Value(
                self.cache.get_or_set(
                    'has_paid_item',
                    lambda: self.items.filter(default_price__gt=0).exists(),
                    3600,
                ),
                output_field=models.BooleanField(),
            )
        ).filter(
            Q(active=True)
            & Q(is_public=True)
            & (
                Q(Q(date_to__isnull=True) & Q(date_from__gte=now() - timedelta(hours=24)))
                | Q(date_to__gte=now() - timedelta(hours=24))
            )
        )  # order_by doesn't make sense with I18nField
        for f in reversed(orderfields):
            if f.startswith('-'):
                subevs = sorted(subevs, key=attrgetter(f[1:]), reverse=True)
            else:
                subevs = sorted(subevs, key=attrgetter(f))
        return subevs

    @property
    def meta_data(self):
        data = {p.name: p.default for p in self.organizer.meta_properties.all()}
        if hasattr(self, 'meta_values_cached'):
            data.update({v.property.name: v.value for v in self.meta_values_cached})
        else:
            data.update({v.property.name: v.value for v in self.meta_values.select_related('property').all()})

        return OrderedDict((k, v) for k, v in sorted(data.items(), key=lambda k: k[0]))

    @property
    def has_payment_provider(self):
        result = False
        for provider in self.get_payment_providers().values():
            if provider.is_enabled and provider.identifier not in (
                'free',
                'boxoffice',
                'offsetting',
                'giftcard',
            ):
                result = True
                break
        return result

    @property
    def has_paid_things(self):
        from .items import Item, ItemVariation

        return (
            Item.objects.filter(event=self, default_price__gt=0).exists()
            or ItemVariation.objects.filter(item__event=self, default_price__gt=0).exists()
        )

    @property
    def talk_schedule_url(self):
        url = urljoin(TALK_HOSTNAME, f'{self.slug}/schedule')
        return url

    @property
    def talk_session_url(self):
        url = urljoin(TALK_HOSTNAME, f'{self.slug}/talk')
        return url

    @property
    def talk_speaker_url(self):
        url = urljoin(TALK_HOSTNAME, f'{self.slug}/speaker')
        return url

    @property
    def talk_dashboard_url(self):
        url = urljoin(TALK_HOSTNAME, f'orga/event/{self.slug}')
        return url

    @property
    def talk_settings_url(self):
        url = urljoin(TALK_HOSTNAME, f'orga/event/{self.slug}/settings')
        return url

    @cached_property
    def live_issues(self):
        from eventyay.base.signals import event_live_issues

        issues = []

        if self.has_paid_things and not self.has_payment_provider:
            issues.append(_('You have configured at least one paid product but have not enabled any payment methods.'))

        if not self.quotas.exists():
            issues.append(_('You need to configure at least one quota to sell anything.'))

        if self.organizer.has_unpaid_invoice():
            issues.append(_('You have unpaid invoices, please pay them before going live.'))

        for mp in self.organizer.meta_properties.all():
            if mp.required and not self.meta_data.get(mp.name):
                issues.append(
                    ('<a {a_attr}>' + gettext('You need to fill the meta parameter "{property}".') + '</a>').format(
                        property=mp.name,
                        a_attr='href="%s#id_prop-%d-value"'
                        % (
                            reverse(
                                'control:event.settings',
                                kwargs={
                                    'organizer': self.organizer.slug,
                                    'event': self.slug,
                                },
                            ),
                            mp.pk,
                        ),
                    )
                )

        gs = GlobalSettingsObject()
        if gs.settings.get('billing_validation', 'True') == 'True':
            billing_obj = OrganizerBillingModel.objects.filter(organizer=self.organizer).first()
            if not billing_obj or not billing_obj.stripe_payment_method_id:
                url = reverse(
                    'control:organizer.settings.billing',
                    kwargs={'organizer': self.organizer.slug},
                )
                issue = format_html(
                    '<a href="{}#tab-0-1-open">{}</a>',
                    url,
                    gettext('You need to fill the billing information.'),
                )
                issues.append(issue)

        responses = event_live_issues.send(self)
        for receiver, response in sorted(responses, key=lambda r: str(r[0])):
            if response:
                issues.append(response)

        return issues

    def get_users_with_any_permission(self):
        """
        Returns a queryset of users who have any permission to this event.

        :return: Iterable of User
        """
        return self.get_users_with_permission(None)

    def get_users_with_permission(self, permission):
        """
        Returns a queryset of users who have a specific permission to this event.

        :return: Iterable of User
        """
        from .auth import User

        if permission:
            kwargs = {permission: True}
        else:
            kwargs = {}

        team_with_perm = Team.objects.filter(members__pk=OuterRef('pk'), organizer=self.organizer, **kwargs).filter(
            Q(all_events=True) | Q(limit_events__pk=self.pk)
        )

        return User.objects.annotate(twp=Exists(team_with_perm)).filter(twp=True)

    def clean_live(self):
        for issue in self.live_issues:
            if issue:
                raise ValidationError(issue)

    def allow_delete(self):
        return not self.orders.exists() and not self.invoices.exists()

    def delete_sub_objects(self):
        self.cartposition_set.filter(addon_to__isnull=False).delete()
        self.cartposition_set.all().delete()
        self.vouchers.all().delete()
        self.items.all().delete()
        self.subevents.all().delete()

    def set_active_plugins(self, modules, allow_restricted=False):
        from eventyay.base.plugins import get_all_plugins

        plugins_active = self.get_plugins()
        plugins_available = {
            p.module: p for p in get_all_plugins(self) if not p.name.startswith('.') and getattr(p, 'visible', True)
        }

        enable = [m for m in modules if m not in plugins_active and m in plugins_available]

        for module in enable:
            if getattr(plugins_available[module].app, 'restricted', False) and not allow_restricted:
                modules.remove(module)
            elif hasattr(plugins_available[module].app, 'installed'):
                getattr(plugins_available[module].app, 'installed')(self)

        self.plugins = ','.join(modules)

    def enable_plugin(self, module, allow_restricted=False):
        plugins_active = self.get_plugins()
        from eventyay.presale.style import regenerate_css

        if module not in plugins_active:
            plugins_active.append(module)
            self.set_active_plugins(plugins_active, allow_restricted=allow_restricted)

        regenerate_css.apply_async(args=(self.pk,))

    def disable_plugin(self, module):
        plugins_active = self.get_plugins()
        from eventyay.presale.style import regenerate_css

        if module in plugins_active:
            plugins_active.remove(module)
            self.set_active_plugins(plugins_active)

        regenerate_css.apply_async(args=(self.pk,))

    @staticmethod
    def clean_has_subevents(event, has_subevents):
        if event is not None and event.has_subevents is not None:
            if event.has_subevents != has_subevents:
                raise ValidationError(_('Once created an event cannot change between an series and a single event.'))

    @staticmethod
    def clean_slug(organizer, event, slug):
        if event is not None and event.slug is not None:
            if event.slug != slug:
                raise ValidationError(_('The event slug cannot be changed.'))
        else:
            if Event.objects.filter(slug=slug, organizer=organizer).exists():
                raise ValidationError(_('This slug has already been used for a different event.'))

    @staticmethod
    def clean_dates(date_from, date_to):
        if date_from is not None and date_to is not None:
            if date_from > date_to:
                raise ValidationError(_('The event cannot end before it starts.'))

    @staticmethod
    def clean_presale(presale_start, presale_end):
        if presale_start is not None and presale_end is not None:
            if presale_start > presale_end:
                raise ValidationError(_("The event's presale cannot end before it starts."))

    def decode_token(self, token, allow_raise=False):
        exc = None
        for jwt_config in self.config["JWT_secrets"]:
            secret = jwt_config["secret"]
            audience = jwt_config["audience"]
            issuer = jwt_config["issuer"]
            try:
                return jwt.decode(
                    token,
                    secret,
                    algorithms=["HS256"],
                    audience=audience,
                    issuer=issuer,
                )
            except jwt.exceptions.ExpiredSignatureError:
                if allow_raise:
                    raise
            except jwt.exceptions.InvalidTokenError as e:
                exc = e
        if exc and allow_raise:
            raise exc

    def has_permission_implicit(
        self,
        *,
        traits,
        permissions: List[Permission],
        room=None,
        allow_empty_traits=True,
    ):
        for role, required_traits in self.trait_grants.items():
            if (
                isinstance(required_traits, list)
                and all(
                    any(x in traits for x in (r if isinstance(r, list) else [r]))
                    for r in required_traits
                )
                and (required_traits or allow_empty_traits)
            ):
                if any(
                    p.value in self.roles.get(role, SYSTEM_ROLES.get(role, []))
                    for p in permissions
                ):
                    return True
        if room:
            for role, required_traits in getattr(room, 'trait_grants', {}).items():
                if (
                    isinstance(required_traits, list)
                    and all(
                        any(x in traits for x in (r if isinstance(r, list) else [r]))
                        for r in required_traits
                    )
                    and (required_traits or allow_empty_traits)
                ):
                    if any(
                        p.value in self.roles.get(role, SYSTEM_ROLES.get(role, []))
                        for p in permissions
                    ):
                        return True

    def has_permission(self, *, user, permission, room=None):
        if getattr(user, 'is_banned', False):
            return False
        if not isinstance(permission, list):
            permission = [permission]
        if getattr(user, 'is_silenced', False) and not any(
            p in MAX_PERMISSIONS_IF_SILENCED for p in permission
        ):
            return False
        if self.has_permission_implicit(
            traits=getattr(user, 'traits', []),
            permissions=permission,
            room=room,
            allow_empty_traits=getattr(user, 'type', None) == getattr(User, 'UserType', None) and user.type == User.UserType.PERSON,
        ):
            return True
        roles = user.get_role_grants(room)
        for r in roles:
            if any(
                p.value in self.roles.get(r, SYSTEM_ROLES.get(r, []))
                for p in permission
            ):
                return True

    async def has_permission_async(self, *, user, permission, room=None):
        if getattr(user, 'is_banned', False):
            return False
        if not isinstance(permission, list):
            permission = [permission]
        if getattr(user, 'is_silenced', False) and not any(
            p in MAX_PERMISSIONS_IF_SILENCED for p in permission
        ):
            return False
        if self.has_permission_implicit(
            traits=getattr(user, 'traits', []),
            permissions=permission,
            room=room,
            allow_empty_traits=getattr(user, 'type', None) == getattr(User, 'UserType', None) and user.type == User.UserType.PERSON,
        ):
            return True
        roles = await user.get_role_grants_async(room)
        for r in roles:
            if any(
                p.value in self.roles.get(r, SYSTEM_ROLES.get(r, []))
                for p in permission
            ):
                return True

    def get_all_permissions(self, user):
        result = defaultdict(set)
        if getattr(user, 'is_banned', False):
            return result
        allow_empty_traits = getattr(user, 'type', None) == getattr(User, 'UserType', None) and user.type == User.UserType.PERSON
        for role, required_traits in self.trait_grants.items():
            if (
                isinstance(required_traits, list)
                and all(
                    any(x in getattr(user, 'traits', [])) for x in (r if isinstance(r, list) else [r])
                    for r in required_traits
                )
                and (required_traits or allow_empty_traits)
            ):
                result[self].update(self.roles.get(role, SYSTEM_ROLES.get(role, [])))
        for grant in getattr(user, 'event_grants', []).all():
            result[self].update(
                self.roles.get(grant.role, SYSTEM_ROLES.get(grant.role, []))
            )
        for room in getattr(self, 'rooms', []).all():
            for role, required_traits in getattr(room, 'trait_grants', {}).items():
                if (
                    isinstance(required_traits, list)
                    and all(
                        any(
                            x in getattr(user, 'traits', [])
                            for x in (r if isinstance(r, list) else [r])
                        )
                        for r in required_traits
                    )
                    and (required_traits or allow_empty_traits)
                ):
                    result[room].update(
                        self.roles.get(role, SYSTEM_ROLES.get(role, []))
                    )
        for grant in getattr(user, 'room_grants', []).select_related("room"):
            result[grant.room].update(
                self.roles.get(grant.role, SYSTEM_ROLES.get(grant.role, []))
            )
        if getattr(user, 'is_silenced', False):
            for key in result.keys():
                result[key] &= MAX_PERMISSIONS_IF_SILENCED
        return result

    def clear_data(self):
        self.audit_logs.all().delete()
        self.event_grants.all().delete()
        self.room_grants.all().delete()
        self.bbb_calls.all().delete()
        ChatEvent.objects.filter(channel__event=self).delete()
        Membership.objects.filter(channel__event=self).delete()
        ExhibitorStaff.objects.filter(exhibitor__event=self).delete()
        PosterPresenter.objects.filter(poster__event=self).delete()
        ContactRequest.objects.filter(exhibitor__event=self).delete()
        ExhibitorView.objects.filter(exhibitor__event=self).delete()
        Reaction.objects.filter(room__event=self).delete()
        RoomView.objects.filter(room__event=self).delete()
        EventView.objects.filter(event=self).delete()
        RoomQuestion.objects.filter(room__event=self).delete()
        Poll.objects.filter(room__event=self).delete()
        Feedback.objects.filter(event=self).delete()
        for f in StoredFile.objects.filter(event=self):
            f.full_delete()
        self.user_set.all().delete()
        self.domain = None
        self.save()

    def clone_from(self, old, new_secrets):
        from eventyay.base.models import Channel
        from eventyay.base.models.storage_model import StoredFile
        if self.pk == old.pk:
            raise ValueError("Illegal attempt to clone into same event")
        def clone_stored_files(*, inst=None, attrs=None, struct=None, url=None):
            if inst and attrs:
                for a in attrs:
                    if getattr(inst, a):
                        setattr(inst, a, clone_stored_files(url=getattr(inst, a)))
            elif url:
                media_base = urljoin(
                    f'http{"" if settings.DEBUG else "s"}://{old.domain}',
                    settings.MEDIA_URL,
                )
                if url.startswith(media_base):
                    mlen = len(media_base)
                    fname = url[mlen:]
                    try:
                        src = StoredFile.objects.get(event=old, file=fname)
                    except StoredFile.DoesNotExist:
                        return url
                    sf = StoredFile.objects.create(
                        event=self,
                        date=src.date,
                        filename=src.filename,
                        type=src.type,
                        file=File(src.file, src.filename),
                        public=src.public,
                        user=None,
                    )
                    return sf.file.url
                else:
                    return url
            elif isinstance(struct, str):
                return clone_stored_files(url=struct)
            elif isinstance(struct, dict):
                return {k: clone_stored_files(struct=v) for k, v in struct.items()}
            elif isinstance(struct, (list, tuple)):
                return [clone_stored_files(struct=e) for e in struct]
            else:
                return struct
        self.config = old.config
        if new_secrets:
            secret = get_random_string(length=64)
            self.config["JWT_secrets"] = [
                {
                    "issuer": "any",
                    "audience": "eventyay",
                    "secret": secret,
                }
            ]
        self.roles = old.roles
        self.trait_grants = old.trait_grants
        self.locale = old.locale
        self.timezone = old.timezone
        self.feature_flags = old.feature_flags
        self.external_auth_url = old.external_auth_url
        self.save()
        room_map = {}
        for r in old.rooms.all():
            try:
                has_channel = r.channel
            except Exception:
                has_channel = False
            old_id = r.pk
            r.pk = None
            r.event = self
            r.module_config = clone_stored_files(struct=r.module_config)
            r.save()
            room_map[old_id] = r
            if has_channel:
                Channel.objects.create(room=r, event=self)
        for r in old.rooms.prefetch_related(
            "exhibitors", "exhibitors__links", "exhibitors__social_media_links"
        ):
            for ex in r.exhibitors.all():
                old_links = list(ex.links.all())
                old_smlinks = list(ex.social_media_links.all())
                ex.pk = None
                ex.event = self
                ex.room = room_map[ex.room_id]
                if ex.highlighted_room_id:
                    ex.highlighted_room = room_map[ex.highlighted_room_id]
                clone_stored_files(
                    inst=ex, attrs=["logo", "banner_list", "banner_detail"]
                )
                ex.text_content = clone_stored_files(struct=ex.text_content)
                ex.save()
                for link in old_smlinks:
                    link.pk = None
                    link.exhibitor = ex
                    link.save()
                for link in old_links:
                    link.pk = None
                    clone_stored_files(inst=link, attrs=["url"])
                    link.exhibitor = ex
                    link.save()


class SubEvent(EventMixin, LoggedModel):
    """
    This model represents a date within an event series.

    :param event: The event this belongs to
    :type event: Event
    :param active: Whether to show the subevent
    :type active: bool
    :param is_public: Whether to show the subevent in lists
    :type is_public: bool
    :param name: This event's full title
    :type name: str
    :param date_from: The datetime this event starts
    :type date_from: datetime
    :param date_to: The datetime this event ends
    :type date_to: datetime
    :param presale_start: No tickets will be sold before this date.
    :type presale_start: datetime
    :param presale_end: No tickets will be sold after this date.
    :type presale_end: datetime
    :param location: venue
    :type location: str
    """

    _event_id = 'event_id'
    event = models.ForeignKey(Event, related_name='subevents', on_delete=models.PROTECT)
    active = models.BooleanField(
        default=False,
        verbose_name=_('Active'),
        help_text=_('Only with this checkbox enabled, this date is visible in the frontend to users.'),
    )
    is_public = models.BooleanField(
        default=True,
        verbose_name=_('Show in lists'),
        help_text=_('If selected, this event will show up publicly on the list of dates for your event.'),
    )
    name = I18nCharField(
        max_length=200,
        verbose_name=_('Name'),
    )
    date_from = models.DateTimeField(verbose_name=_('Event start time'))
    date_to = models.DateTimeField(null=True, blank=True, verbose_name=_('Event end time'))
    date_admission = models.DateTimeField(null=True, blank=True, verbose_name=_('Admission time'))
    presale_end = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('End of presale'),
        help_text=_(
            'Optional. No products will be sold after this date. If you do not set this value, the presale '
            'will end after the end date of your event.'
        ),
    )
    presale_start = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Start of presale'),
        help_text=_('Optional. No products will be sold before this date.'),
    )
    location = I18nTextField(
        null=True,
        blank=True,
        max_length=200,
        verbose_name=_('Location'),
    )
    geo_lat = models.FloatField(
        verbose_name=_('Latitude'),
        null=True,
        blank=True,
        validators=[
            MinValueValidator(-90),
            MaxValueValidator(90),
        ],
    )
    geo_lon = models.FloatField(
        verbose_name=_('Longitude'),
        null=True,
        blank=True,
        validators=[
            MinValueValidator(-180),
            MaxValueValidator(180),
        ],
    )
    frontpage_text = I18nTextField(null=True, blank=True, verbose_name=_('Frontpage text'))
    seating_plan = models.ForeignKey(
        'SeatingPlan',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='subevents',
    )
    last_modified = models.DateTimeField(auto_now=True, db_index=True)

    items = models.ManyToManyField('Item', through='SubEventItem')
    variations = models.ManyToManyField('ItemVariation', through='SubEventItemVariation')

    objects = ScopedManager(organizer='event__organizer')

    class Meta:
        verbose_name = _('Date in event series')
        verbose_name_plural = _('Dates in event series')
        ordering = ('date_from', 'name')

    def __str__(self):
        return '{} - {} {}'.format(
            self.name,
            self.get_date_range_display(),
            (date_format(self.date_from.astimezone(self.timezone), 'TIME_FORMAT') if self.settings.show_times else ''),
        ).strip()

    def _seats(self, ignore_voucher=None):
        from .seating import Seat

        qs_annotated = Seat.annotated(
            self.seats,
            self.event_id,
            self,
            ignore_voucher_id=ignore_voucher.pk if ignore_voucher else None,
            minimal_distance=self.settings.seating_minimal_distance,
            distance_only_within_row=self.settings.seating_distance_within_row,
        )
        return qs_annotated

    @cached_property
    def settings(self):
        return self.event.settings

    @cached_property
    def item_overrides(self):
        from .items import SubEventItem

        return {si.item_id: si for si in SubEventItem.objects.filter(subevent=self)}

    @cached_property
    def var_overrides(self):
        from .items import SubEventItemVariation

        return {si.variation_id: si for si in SubEventItemVariation.objects.filter(subevent=self)}

    @property
    def item_price_overrides(self):
        return {si.item_id: si.price for si in self.item_overrides.values() if si.price is not None}

    @property
    def var_price_overrides(self):
        return {si.variation_id: si.price for si in self.var_overrides.values() if si.price is not None}

    @property
    def meta_data(self):
        data = self.event.meta_data
        data.update({v.property.name: v.value for v in self.meta_values.select_related('property').all()})
        return data

    @property
    def currency(self):
        return self.event.currency

    def allow_delete(self):
        return not self.orderposition_set.exists()

    def delete(self, *args, **kwargs):
        clear_cache = kwargs.pop('clear_cache', False)
        super().delete(*args, **kwargs)
        if self.event and clear_cache:
            self.event.cache.clear()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__original_dates = (self.date_from, self.date_to)

    def save(self, *args, **kwargs):
        from .orders import Order

        clear_cache = kwargs.pop('clear_cache', False)
        super().save(*args, **kwargs)
        if self.event and clear_cache:
            self.event.cache.clear()

        if (self.date_from, self.date_to) != self.__original_dates:
            """
            This is required to guarantee a synchronization invariant of our scanning apps.
            Our syncing apps throw away order records of subevents more than X days ago, since
            they are not interesting for ticket scanning and pose a performance hazard. However,
            the app needs to know when a subevent is moved to a date in the future, since that
            might require it to re-download and re-store the orders.
            """
            Order.objects.filter(all_positions__subevent=self).update(last_modified=now())

    @staticmethod
    def clean_items(event, items):
        for item in items:
            if event != item.event:
                raise ValidationError(_('One or more items do not belong to this event.'))

    @staticmethod
    def clean_variations(event, variations):
        for variation in variations:
            if event != variation.item.event:
                raise ValidationError(_('One or more variations do not belong to this event.'))


@scopes_disabled()
def generate_invite_token():
    return get_random_string(length=32, allowed_chars=string.ascii_lowercase + string.digits)


class EventLock(models.Model):
    event = models.CharField(max_length=36, primary_key=True)
    date = models.DateTimeField(auto_now=True)
    token = models.UUIDField(default=uuid.uuid4)


class RequiredAction(models.Model):
    """
    Represents an action that is to be done by an admin. The admin will be
    displayed a list of actions to do.

    :param datatime: The timestamp of the required action
    :type datetime: datetime
    :param user: The user that performed the action
    :type user: User
    :param done: If this action has been completed or dismissed
    :type done: bool
    :param action_type: The type of action that has to be performed. This is
       used to look up the renderer used to describe the action in a human-
       readable way. This should be some namespaced value using dotted
       notation to avoid duplicates, e.g.
       ``"eventyay.plugins.banktransfer.incoming_transfer"``.
    :type action_type: str
    :param data: Arbitrary data that can be used by the log action renderer
    :type data: str
    """

    datetime = models.DateTimeField(auto_now_add=True, db_index=True)
    done = models.BooleanField(default=False)
    user = models.ForeignKey('User', null=True, blank=True, on_delete=models.PROTECT)
    event = models.ForeignKey('Event', null=True, blank=True, on_delete=models.CASCADE)
    action_type = models.CharField(max_length=255)
    data = models.TextField(default='{}')

    class Meta:
        ordering = ('datetime',)

    def display(self, request):
        from ..signals import requiredaction_display

        for receiver, response in requiredaction_display.send(self.event, action=self, request=request):
            if response:
                return response
        return self.action_type

    def save(self, *args, **kwargs):
        created = not self.pk
        super().save(*args, **kwargs)
        if created:
            from ..services.notifications import notify
            from .log import LogEntry

            logentry = LogEntry.objects.create(
                content_object=self,
                action_type='eventyay.event.action_required',
                event=self.event,
                visible=False,
            )
            notify.apply_async(args=(logentry.pk,))


class EventMetaProperty(LoggedModel):
    """
    An organizer account can have EventMetaProperty objects attached to define meta information fields
    for its events. This information can be re-used for example in ticket layouts.

    :param organizer: The organizer this property is defined for.
    :type organizer: Organizer
    :param name: Name
    :type name: Name of the property, used in various places
    :param default: Default value
    :type default: str
    """

    organizer = models.ForeignKey(Organizer, related_name='meta_properties', on_delete=models.CASCADE)
    name = models.CharField(
        max_length=50,
        db_index=True,
        help_text=_('Can not contain spaces or special characters except underscores'),
        validators=[
            RegexValidator(
                regex='^[a-zA-Z0-9_]+$',
                message=_('The property name may only contain letters, numbers and underscores.'),
            ),
        ],
        verbose_name=_('Name'),
    )
    default = models.TextField(blank=True, verbose_name=_('Default value'))
    protected = models.BooleanField(
        default=False,
        verbose_name=_('Can only be changed by organizer-level administrators'),
    )
    required = models.BooleanField(
        default=False,
        verbose_name=_('Required for events'),
        help_text=_(
            'If checked, an event can only be taken live if the property is set. In event series, its always '
            'optional to set a value for individual dates'
        ),
    )
    allowed_values = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('Valid values'),
        help_text=_('If you keep this empty, any value is allowed. Otherwise, enter one possible value per line.'),
    )

    def full_clean(self, exclude=None, validate_unique=True):
        super().full_clean(exclude, validate_unique)
        if self.default and self.required:
            raise ValidationError(_('A property can either be required or have a default value, not both.'))
        if self.default and self.allowed_values and self.default not in self.allowed_values.splitlines():
            raise ValidationError(_('You cannot set a default value that is not a valid value.'))


class EventMetaValue(LoggedModel):
    """
    A meta-data value assigned to an event.

    :param event: The event this metadata is valid for
    :type event: Event
    :param property: The property this value belongs to
    :type property: EventMetaProperty
    :param value: The actual value
    :type value: str
    """

    event = models.ForeignKey('Event', on_delete=models.CASCADE, related_name='meta_values')
    property = models.ForeignKey('EventMetaProperty', on_delete=models.CASCADE, related_name='event_values')
    value = models.TextField()

    class Meta:
        unique_together = ('event', 'property')

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        if self.event:
            self.event.cache.clear()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.event:
            self.event.cache.clear()


class SubEventMetaValue(LoggedModel):
    """
    A meta-data value assigned to a sub-event.

    :param event: The event this metadata is valid for
    :type event: Event
    :param property: The property this value belongs to
    :type property: EventMetaProperty
    :param value: The actual value
    :type value: str
    """

    subevent = models.ForeignKey('SubEvent', on_delete=models.CASCADE, related_name='meta_values')
    property = models.ForeignKey('EventMetaProperty', on_delete=models.CASCADE, related_name='subevent_values')
    value = models.TextField()

    class Meta:
        unique_together = ('subevent', 'property')

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        if self.subevent:
            self.subevent.event.cache.clear()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.subevent:
            self.subevent.event.cache.clear()


class EventPlannedUsage(models.Model):
    event = models.ForeignKey(
        'Event', on_delete=models.CASCADE, related_name="planned_usages"
    )
    start = models.DateField()
    end = models.DateField()
    attendees = models.PositiveIntegerField()
    notes = models.TextField(blank=True)
    class Meta:
        ordering = ("start",)
    def as_ical(self):
        event = icalendar.Event()
        event["uid"] = f"{self.event.id}-{self.id}"
        event["dtstart"] = self.start
        event["dtend"] = self.start
        event["summary"] = self.event.name if hasattr(self.event, 'name') else self.event.title
        event["description"] = self.notes
        event["url"] = self.event.domain
        return event

class EventView(models.Model):
    event = models.ForeignKey(
        'Event', related_name="views", on_delete=models.CASCADE
    )
    start = models.DateTimeField(
        auto_now_add=True,
    )
    end = models.DateTimeField(
        null=True, db_index=True
    )
    user = models.ForeignKey(
        'User', related_name="event_views", on_delete=models.CASCADE
    )
    class Meta:
        indexes = [
            models.Index(fields=["start"]),
        ]
