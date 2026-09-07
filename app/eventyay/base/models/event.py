import copy
import datetime as dt
import hashlib
import logging
import os
import string
import uuid
from collections import OrderedDict, defaultdict
from contextlib import suppress
from datetime import datetime, time, timedelta
from operator import attrgetter
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import icalendar
import jwt
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned, SuspiciousFileOperation, ValidationError
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.mail import get_connection
from django.core.validators import (
    MaxValueValidator,
    MinLengthValidator,
    MinValueValidator,
    RegexValidator,
)
from django.db import models, transaction
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
from django_scopes import ScopedManager, scope, scopes_disabled
from i18nfield.fields import I18nCharField, I18nTextField
from redis.exceptions import RedisError
from rules.contrib.models import RulesModelBase, RulesModelMixin

from eventyay.base.models.base import LoggedModel
from eventyay.base.models.fields import MultiStringField
from eventyay.base.models.mixins import FileCleanupMixin, TimestampedModel
from eventyay.base.plugins import get_all_plugins
from eventyay.base.reldate import RelativeDateWrapper
from eventyay.base.settings import GlobalSettingsObject
from eventyay.base.validators import EventSlugBanlistValidator
from eventyay.common.language import LANGUAGE_NAMES
from eventyay.common.text.path import path_with_hash, resolve_media_path as _resolve_media_path
from eventyay.common.text.phrases import phrases
from eventyay.common.urls import EventUrls, is_http_url
from eventyay.consts import TIMEZONE_CHOICES
from eventyay.core.permissions import (
    MAX_PERMISSIONS_IF_SILENCED,
    ORGANIZER_ROLES,
    SYSTEM_ROLES,
    Permission,
    default_grants,
    default_roles,
    normalize_permission_value,
    traits_match_required,
)
from eventyay.core.utils.json import CustomJSONEncoder
from eventyay.eventyay_common.video.permissions import (
    VIDEO_TRAIT_ROLE_MAP,
    resolve_attendee_trait_grant,
)
from eventyay.helpers.database import GroupConcat
from eventyay.helpers.daterange import daterange
from eventyay.helpers.http import smtp_reachable
from eventyay.helpers.json import safe_string
from eventyay.helpers.thumb import ThumbnailError, get_thumbnail
from eventyay.talk_rules.event import (
    can_change_event_settings,
    can_create_events,
    has_any_permission,
    has_talk_permission,
    is_event_visible,
)

from ..settings import settings_hierarkey
from .auth import User
from .mixins import OrderedModel, PretalxModel
from .organizer import Organizer, Team
from .roomquestion import RoomQuestion
from .systemlog import SystemLog


TALK_HOSTNAME = settings.TALK_HOSTNAME
logger = logging.getLogger(__name__)


def event_css_path(instance, filename):
    return path_with_hash(filename, base_path=f'{instance.slug}/css/')


def event_logo_path(instance, filename):
    return path_with_hash(filename, base_path=f'{instance.slug}/img/')


FEATURE_FLAGS = [
    'schedule-control',
    'roulette',
    'muxdata',
    'page.landing',
    'zoom',
    'janus',
    'jitsi',
    'polls',
    'conftool',
    'cross-origin-isolation',
]


def default_feature_flags():
    return {
        'show_schedule': True,
        'show_featured': 'never',
        'show_featured_speakers': 'never',
        'show_widget_if_not_public': False,
        'session_popularity_enabled': False,
        'session_popularity_show_on_schedule': True,
        'export_html_on_release': False,
        'use_tracks': True,
        'use_feedback': True,
        'use_submission_comments': True,
        'present_multiple_times': False,
        'submission_public_review': True,
        'chat-moderation': True,
        'polls': True,
        'schedule-control': True,
        'etherpad_enabled': False,
        'etherpad_auto_generate': False,
    }


def default_display_settings():
    return {
        'schedule': 'grid',
        'imprint_url': None,
        'header_pattern': '',
        'html_export_url': '',
        'texts': {'agenda_session_above': '', 'agenda_session_below': ''},
        'etherpad_public': False,
    }


def default_review_settings():
    return {
        'score_mandatory': False,
        'text_mandatory': False,
        'aggregate_method': 'median',
        'score_format': 'words_numbers',
    }


def default_mail_settings():
    return {
        'mail_from': '',
        'reply_to': '',
        'signature': '',
        'subject_prefix': '',
        'smtp_use_custom': '',
        'smtp_host': '',
        'smtp_port': 587,
        'smtp_username': '',
        'smtp_password': '',
        'smtp_use_tls': '',
        'smtp_use_ssl': '',
        'mail_on_new_submission': False,
    }


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
        tz = tz or ZoneInfo(key=self.settings.timezone)
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
        tz = tz or ZoneInfo(key=self.settings.timezone)
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
        if isinstance(tz, str):
            tz = ZoneInfo(key=tz)
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
        if isinstance(tz, str):
            tz = ZoneInfo(key=tz)
        return _date(self.date_from.astimezone(tz), 'TIME_FORMAT')

    def get_date_to_display(self, tz=None, show_times=True, short=False) -> str:
        """
        Returns a formatted string containing the start date of the event with respect
        to the current locale and to the ``show_times`` setting. Returns an empty string
        if ``show_date_to`` is ``False``.
        """
        tz = tz or self.timezone
        if isinstance(tz, str):
            tz = ZoneInfo(key=tz)
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
        tz = tz or ZoneInfo(key=self.settings.timezone)
        if isinstance(tz, str):
            tz = ZoneInfo(key=tz)
        if (not self.settings.show_date_to and not force_show_end) or not self.date_to:
            return _date(self.date_from.astimezone(tz), 'DATE_FORMAT')
        return daterange(self.date_from.astimezone(tz), self.date_to.astimezone(tz))

    @property
    def timezone(self):
        return ZoneInfo(key=self.settings.timezone)

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
        from eventyay.base.models import Product, ProductVariation, Quota

        sq_active_product = (
            Product.objects.using(settings.DATABASE_REPLICA)
            .filter_available(channel=channel)
            .filter(Q(variations__isnull=True) & Q(quotas__pk=OuterRef('pk')))
            .order_by()
            .values_list('quotas__pk')
            .annotate(products=GroupConcat('pk', delimiter=','))
            .values('products')
        )
        sq_active_variation = (
            ProductVariation.objects.filter(
                Q(active=True)
                & Q(product__active=True)
                & Q(Q(product__available_from__isnull=True) | Q(product__available_from__lte=now()))
                & Q(Q(product__available_until__isnull=True) | Q(product__available_until__gte=now()))
                & Q(Q(product__category__isnull=True) | Q(product__category__is_addon=False))
                & Q(product__sales_channels__contains=channel)
                & Q(product__hide_without_voucher=False)
                & Q(product__require_bundling=False)
                & Q(quotas__pk=OuterRef('pk'))
            )
            .order_by()
            .values_list('quotas__pk')
            .annotate(products=GroupConcat('pk', delimiter=','))
            .values('products')
        )
        return qs.annotate(
            has_paid_product=Exists(Product.objects.filter(event_id=OuterRef(cls._event_id), default_price__gt=0))
        ).prefetch_related(
            Prefetch(
                'quotas',
                to_attr='active_quotas',
                queryset=Quota.objects.using(settings.DATABASE_REPLICA)
                .annotate(
                    active_products=Subquery(sq_active_product, output_field=models.TextField()),
                    active_variations=Subquery(sq_active_variation, output_field=models.TextField()),
                )
                .exclude(Q(active_products='') & Q(active_variations=''))
                .select_related('event', 'subevent'),
            )
        )

    @cached_property
    def best_availability_state(self):
        from .product import Quota

        if not hasattr(self, 'active_quotas'):
            raise TypeError('Call this only if you fetched the subevents via Event/SubEvent.annotated()')
        products_available = set()
        vars_available = set()
        products_reserved = set()
        vars_reserved = set()
        products_gone = set()
        vars_gone = set()

        r = getattr(self, '_quota_cache', {})
        for q in self.active_quotas:
            res = r[q] if q in r else q.availability(allow_cache=True)

            if res[0] == Quota.AVAILABILITY_OK:
                if q.active_products:
                    products_available.update(q.active_products.split(','))
                if q.active_variations:
                    vars_available.update(q.active_variations.split(','))
            elif res[0] == Quota.AVAILABILITY_RESERVED:
                if q.active_products:
                    products_reserved.update(q.active_products.split(','))
                if q.active_variations:
                    vars_available.update(q.active_variations.split(','))
            elif res[0] < Quota.AVAILABILITY_RESERVED:
                if q.active_products:
                    products_gone.update(q.active_products.split(','))
                if q.active_variations:
                    vars_gone.update(q.active_variations.split(','))
        if not self.active_quotas:
            return None
        if products_available - products_reserved - products_gone or vars_available - vars_reserved - vars_gone:
            return Quota.AVAILABILITY_OK
        if products_reserved - products_gone or vars_reserved - vars_gone:
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


# We don't subclass PretalxModel because:
# - We want to avoid the `objects = ScopedManager()` (we may use it later, after the making "enext" stable enough).
# - We don't want to inherit the LogMixin (already have LoggedModel).
@settings_hierarkey.add(parent_field='organizer', cache_namespace='event')

class Event(
    EventMixin, LoggedModel, TimestampedModel, FileCleanupMixin, RulesModelMixin, models.Model, metaclass=RulesModelBase
):
    """
    This model represents an event. An event is anything you can buy
    tickets for.

    :param organizer: The organizer this event belongs to
    :type organizer: eventyay.base.models.organizer.Organizer
    :param testmode: This event is in test mode
    :type testmode: bool
    :param private_testmode: This event hides tickets from non-organizers
    :type private_testmode: bool
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
    :type date_from: datetime.datetime
    :param date_to: The datetime this event ends
    :type date_to: datetime.datetime
    :param presale_start: No tickets will be sold before this date.
    :type presale_start: datetime.datetime
    :param presale_end: No tickets will be sold after this date.
    :type presale_end: datetime.datetime
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
    private_testmode = models.BooleanField(default=False)
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
    startpage_visible = models.BooleanField(default=True, verbose_name=_('Visible on start page'))
    startpage_featured = models.BooleanField(default=False, verbose_name=_('Featured on start page'))
    tickets_published = models.BooleanField(default=False, verbose_name=_('Tickets are published'))
    talks_published = models.BooleanField(default=False, verbose_name=_('Talk pages are published'))
    currency = models.CharField(
        max_length=10,
        verbose_name=_('Event currency'),
        choices=CURRENCY_CHOICES,
        default=settings.DEFAULT_CURRENCY,
    )
    date_from = models.DateTimeField(verbose_name=_('Event start time'))
    date_to = models.DateTimeField(verbose_name=_('Event end time'))
    date_admission = models.DateTimeField(null=True, blank=True, verbose_name=_('Admission time'))
    is_public = models.BooleanField(
        default=True,
        verbose_name=_('Show in lists'),
        help_text='If selected, this event will show up publicly on the list of events for your organizer account.',
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
    banned_users = models.ManyToManyField(
        'User',
        related_name='banned_events',
        blank=True,
        verbose_name=_('Banned users'),
        help_text=_('Users who are banned from submitting feedback or interacting with this event.'),
    )

    # Fields for talk
    timezone = models.CharField(
        choices=[(tz, tz) for tz in TIMEZONE_CHOICES],
        max_length=32,
        default='UTC',
        help_text=_('All event dates will be localised and interpreted to be in this timezone.'),
    )
    email = models.EmailField(
        verbose_name=_('Organizer email address'),
        help_text=_("Enter an organizer email address for event-related emails. "
                    "If set, this address will be used as the Reply-To when the platform sender address is used. "
                    "If left empty, no Reply-To will be added automatically and replies will go to the sender address (platform default if not customized)."),
        blank=True,
        null=True,
    )
    custom_domain = models.URLField(
        verbose_name=_('Custom domain'),
        help_text=_('Enter a custom domain, such as https://my.event.example.org'),
        null=True,
        blank=True,
    )
    display_settings = models.JSONField(default=default_display_settings)
    review_settings = models.JSONField(default=default_review_settings)
    mail_settings = models.JSONField(default=default_mail_settings)
    primary_color = models.CharField(
        max_length=7,
        null=True,
        blank=True,
        validators=[
            RegexValidator('#([0-9A-Fa-f]{3}){1,2}'),
        ],
        verbose_name=_('Main event colour'),
        help_text=_('Provide a hex value like #00ff00 if you want to style eventyay in your event’s colour scheme.'),
    )
    custom_css = models.FileField(
        upload_to=event_css_path,
        null=True,
        blank=True,
        verbose_name=_('Custom Event CSS'),
        help_text=_('Upload a custom CSS file if changing the primary colour is not sufficient for you.'),
    )
    logo = models.ImageField(
        upload_to=event_logo_path,
        null=True,
        blank=True,
        verbose_name=_('Logo'),
        help_text=_(
            'When you upload a logo, the event name and date will not appear in the header. '
            'The logo scales to 140 px in height while maintaining aspect ratio.'
        ),
    )
    header_image = models.ImageField(
        upload_to=event_logo_path,
        null=True,
        blank=True,
        verbose_name=_('Header image'),
        help_text=_(
            'This image appears at the top of all event pages, replacing the default color or pattern. '
            'It is center-aligned and not stretched, ensuring the middle part remains visible on smaller screens. '
            'We recommend an image at least 1170 px wide and 120 px in height for best results.'
        ),
    )
    locale_array = models.TextField(default=settings.LANGUAGE_CODE)
    content_locale_array = models.TextField(default=settings.LANGUAGE_CODE)
    locale = models.CharField(
        max_length=32,
        default=settings.LANGUAGE_CODE,
        choices=settings.LANGUAGES,
        verbose_name=_('Default language'),
    )

    # Virtual platform fields
    config = models.JSONField(null=True, blank=True)
    roles = models.JSONField(null=True, blank=True, default=default_roles, encoder=CustomJSONEncoder)
    trait_grants = models.JSONField(null=True, blank=True, default=default_grants)
    domain = models.CharField(
        max_length=250,
        unique=True,
        null=True,
        blank=True,
        validators=[RegexValidator(regex=r'^[a-z0-9-.:]+(/[a-zA-Z0-9-_./]*)?$')],
    )
    feature_flags = models.JSONField(default=default_feature_flags)
    external_auth_url = models.URLField(null=True, blank=True)

    HEADER_PATTERN_CHOICES = (
        ('', _('Plain')),
        ('pcb', _('Circuits')),
        ('bubbles', _('Circles')),
        ('signal', _('Signal')),
        ('topo', _('Topography')),
        ('graph', _('Graph Paper')),
    )

    class urls(EventUrls):
        """URL patterns for public/frontend views of this event."""

        base_path = settings.BASE_PATH
        base = '{base_path}/{self.organizer.slug}/{self.slug}/'
        login = '{base}login/'
        logout = '{base}logout'
        auth = '{base}auth/'
        logo = '{self.logo.url}'
        social_image = '{base}og-image'
        reset = '{base}reset'
        submit = '{base}submit/'
        user = '{base}me/'
        user_submissions = '{user}submissions/'
        user_mails = '{user}mails/'
        schedule = '{base}schedule/'
        schedule_nojs = '{schedule}nojs'
        featured = '{base}featured/'
        talks = '{base}sessions/'
        speakers = '{base}speakers/'
        changelog = '{schedule}changelog/'
        feed = '{schedule}feed.xml'
        export = '{schedule}export/'
        frab_xml = '{export}schedule.xml'
        frab_json = '{export}schedule.json'
        frab_xcal = '{export}schedule.xcal'
        ical = '{export}schedule.ics'
        schedule_widget_data = '{schedule}widgets/schedule.json'
        schedule_widget_script = '{base}widgets/schedule.js'
        settings_css = '{base}static/event.css'
        video_base = '{base}video/'

    class orga_urls(EventUrls):
        """URL patterns for organizer/admin panel views of this event."""

        base_path = settings.BASE_PATH
        base = '{base_path}/orga/event/{self.organizer.slug}/{self.slug}/'
        login = '{base}login/'
        live = '{base}live'
        delete = '{base}delete'
        cfp = '{base}cfp/'
        history = '{base}history/'
        users = '{base}api/users'
        mail = '{base}mails/'
        compose_mails = '{mail}compose'
        compose_mails_sessions = '{compose_mails}/sessions/'
        compose_mails_sessions_recipients = '{compose_mails}/sessions/recipients'
        compose_mails_teams = '{compose_mails}/teams/'
        send_drafts_reminder = '{compose_mails}/reminders'
        mail_templates = '{mail}templates/'
        new_template = '{mail_templates}new/'
        outbox = '{mail}outbox/'
        drafts = '{mail}drafts/'
        sent_mails = '{mail}sent'
        send_outbox = '{outbox}send'
        purge_outbox = '{outbox}purge'
        submissions = '{base}submissions/'
        tags = '{submissions}tags/'
        new_tag = '{tags}new/'
        submission_cards = '{base}submissions/cards/'
        submission_feed = '{base}submissions/feed/'
        new_submission = '{submissions}new'
        feedback = '{submissions}feedback/'
        apply_pending = '{submissions}apply-pending/'
        speakers = '{base}speakers/'
        settings = edit_settings = '{base}settings/'
        review_settings = '{settings}review/'
        feedback_settings = '{settings}feedback/'
        mail_settings = edit_mail_settings = '{settings}mail'
        widget_settings = '{settings}widget'
        import_export_settings = '{settings}import-export/'
        import_export_schedule_export_trigger = '{import_export_settings}schedule/export/trigger'
        import_export_schedule_export_download = '{import_export_settings}schedule/export/download'
        team_settings = '{settings}team/'
        new_team = '{settings}team/new'
        room_settings = '{schedule}rooms/'
        new_room = '{room_settings}new/'
        schedule = '{base}schedule/'
        schedule_export = '{import_export_settings}?export_target=session#tab-export'
        schedule_export_trigger = '{import_export_schedule_export_trigger}'
        schedule_export_download = '{import_export_schedule_export_download}'
        release_schedule = '{schedule}release'
        reset_schedule = '{schedule}reset'
        toggle_schedule = '{schedule}toggle'
        reviews = '{base}reviews/'
        review_assignments = '{reviews}assign/'
        schedule_api = '{base}schedule/api/'
        talks_api = '{schedule_api}talks/'
        plugins = '{settings}plugins'
        information = '{base}info/'
        new_information = '{base}info/new/'

    class api_urls(EventUrls):
        """URL patterns for API endpoints related to this event."""

        base_path = settings.TALK_BASE_PATH
        base = '{base_path}/api/v1/events/{self.slug}/'
        submissions = '{base}submissions/'
        slots = '{base}slots/'
        talks = '{base}talks/'
        schedules = '{base}schedules/'
        speakers = '{base}speakers/'
        reviews = '{base}reviews/'
        rooms = '{base}rooms/'
        questions = '{base}talkquestions/'
        question_options = '{base}question-options/'
        answers = '{base}answers/'
        tags = '{base}tags/'
        tracks = '{base}tracks/'
        submission_types = '{base}submission-types/'
        mail_templates = '{base}mail-templates/'
        access_codes = '{base}access-codes/'
        speaker_information = '{base}speaker-information/'

    class tickets_urls(EventUrls):
        """URL patterns for ticket/control panel views of this event."""

        _full_base_path = settings.BASE_PATH
        base_path = urlparse(_full_base_path).path.rstrip('/')
        base = '{base_path}/control/'
        common = '{base_path}/common/'
        tickets_home_common = '{common}events/{self.organiser.slug}/{self.slug}/'
        tickets_dashboard_url = '{base}event/{self.organiser.slug}/{self.slug}/'
        tickets_home_common = '{common}event/{self.organizer.slug}/{self.slug}/'
        tickets_dashboard_url = '{base}event/{self.organizer.slug}/{self.slug}/'

    class Meta:
        verbose_name = _('Event')
        verbose_name_plural = _('Events')
        ordering = ('date_from', 'name')
        unique_together = (('organizer', 'slug'),)

        # Note: The views which use these permissions need to revisit the permission names.
        # The permission names change when we move the code to a different app.
        rules_permissions = {
            'orga_access': has_any_permission,
            'talk_orga_access': has_talk_permission,
            'view': is_event_visible | has_any_permission,
            'update': can_change_event_settings,
            'create': can_create_events,
        }

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
        self.settings.ticket_download = True
        self.settings.private_testmode_tickets = False
        self.settings.private_testmode_talks = False

    @property
    def social_image(self):
        from eventyay.multidomain.urlreverse import build_absolute_uri

        img = None
        og_file = self.settings.get('og_image', as_type=str, default=None)
        if og_file:
            if is_http_url(og_file):
                return og_file
            
            og_path = _resolve_media_path(og_file)
            if og_path:
                try:
                    img = get_thumbnail(og_path, '1200').thumb.url
                except (OSError, SuspiciousFileOperation, ThumbnailError) as exc:
                    logger.warning('Failed to load og_image thumbnail for %s: %s', og_path, exc)

        if not img:
            if self.visible_logo_url:
                img = self.visible_logo_url
            elif self.visible_header_image_url:
                img = self.visible_header_image_url

        if img:
            if is_http_url(img):
                return img
            if urlparse(img).scheme:
                return None
            return urljoin(build_absolute_uri(self, 'presale:event.index'), img)

    @property
    def social_image_signature(self):
        og_image = self.settings.get('og_image', as_type=str, default='') or ''
        image_source = og_image or self.visible_logo_url or self.visible_header_image_url or ''
        if not image_source:
            return ''
        return hashlib.sha1(image_source.encode('utf-8')).hexdigest()[:12]

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
        was_created = not bool(self.pk)
        locales_changed = False
        
        # Check if locales have changed by comparing locale_array directly
        if not was_created:
            try:
                old_instance = self.__class__.objects.get(pk=self.pk)
                # Compute locales directly from locale_array to avoid cached_property issues
                old_locales = set(code for code in old_instance.locale_array.split(',') if code)
                new_locales = set(code for code in self.locale_array.split(',') if code)
                if old_locales != new_locales:
                    locales_changed = True
            except self.__class__.DoesNotExist:
                pass
        
        if self.date_from and not self.date_to:
            self.date_to = self.date_from + timedelta(hours=24)

        obj = super().save(*args, **kwargs)
        self.cache.clear()
        
        # Clear cached_property for locales and related properties to ensure fresh calculation
        if 'locales' in self.__dict__:
            del self.__dict__['locales']
        if 'content_locales' in self.__dict__:
            del self.__dict__['content_locales']

        if was_created:
            self.build_initial_data()
        elif locales_changed:
            # Backfill all existing mail templates with new locales
            self._backfill_all_mail_template_locales()
        
        return obj

    def _backfill_all_mail_template_locales(self):
        """Backfill all existing mail templates with newly added locales."""
        with scope(event=self):
            for template in self.mail_templates.all():
                if template.role:
                    self._ensure_mail_template_locales(template, template.role)

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

    def lock(self, blocking=False, blocking_timeout=None):
        """
        Returns a contextmanager that can be used to lock an event for bookings.
        """
        from eventyay.base.services import locking

        return locking.LockManager(self, blocking=blocking, blocking_timeout=blocking_timeout)

    def __getstate__(self):
        """
        Custom pickle method to exclude unpicklable cached properties like 'cache'
        which contains thread locks that cannot be serialized.
        """
        state = self.__dict__.copy()
        # Remove the cache property if it has been accessed (it contains unpicklable thread locks)
        state.pop('cache', None)
        return state

    def __setstate__(self, state):
        """
        Custom unpickle method to restore the Event instance.
        The cache property will be recreated on first access thanks to @cached_property.
        """
        self.__dict__.update(state)

    def get_mail_backend(self, timeout=None, force_custom=False):
        """
        Returns an email server connection, either by using the system-wide connection
        or by returning a custom one based on the event's settings.
        """
        from eventyay.base.email import CustomSMTPBackend, SendGridEmail
        from eventyay.base.gmail.resolver import get_gmail_mail_backend

        gs = GlobalSettingsObject()

        if self.settings.smtp_use_custom or force_custom:
            if self.settings.email_vendor == 'gmail_api':
                backend = get_gmail_mail_backend(event=self, timeout=timeout, force_custom=force_custom)
                if backend:
                    return backend
            if self.settings.email_vendor == 'sendgrid':
                return SendGridEmail(api_key=self.settings.send_grid_api_key)
            if not force_custom and not smtp_reachable(self.settings.smtp_host, self.settings.smtp_port, timeout=timeout):
                logger.warning(
                    'Event SMTP %s:%s is not reachable, falling back to system email backend',
                    self.settings.smtp_host,
                    self.settings.smtp_port,
                )
                return get_connection(fail_silently=False, timeout=timeout)
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
            if gs.settings.email_vendor == 'gmail_api':
                backend = get_gmail_mail_backend(timeout=timeout)
                if backend:
                    return backend
            if gs.settings.email_vendor == 'sendgrid':
                return SendGridEmail(api_key=gs.settings.send_grid_api_key)
            if not smtp_reachable(gs.settings.smtp_host, gs.settings.smtp_port, timeout=timeout):
                logger.warning(
                    'Global SMTP %s:%s is not reachable, falling back to system email backend',
                    gs.settings.smtp_host,
                    gs.settings.smtp_port,
                )
                return get_connection(fail_silently=False, timeout=timeout)
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
        return get_connection(fail_silently=False, timeout=timeout)

    @property
    def payment_term_last(self):
        """
        The last datetime of payments for this event.
        """
        tz = ZoneInfo(key=self.settings.timezone)
        return make_aware(
            datetime.combine(
                self.settings.get('payment_term_last', as_type=RelativeDateWrapper).datetime(self).date(),
                time(hour=23, minute=59, second=59),
            ),
            tz,
        )

    def copy_data_from(self, other, clone_options=None):
        from ..signals import event_copy_data
        from . import (
            Product,
            ProductAddOn,
            ProductBundle,
            ProductCategory,
            ProductMetaValue,
            Question,
            Quota,
        )

        clone_options = clone_options or {}
        clone_common = clone_options.get('clone_common_data', True)
        clone_settings = clone_options.get('clone_settings', True)
        clone_design_texts = clone_options.get('clone_design_texts', True)
        clone_email_settings = clone_options.get('clone_email_settings', True)
        
        clone_ticketing = clone_options.get('clone_ticketing_data', True)
        clone_products = clone_options.get('clone_products', True)
        clone_questions = clone_options.get('clone_questions', True)
        clone_checkin_lists = clone_options.get('clone_checkin_lists', True)
        clone_payment_settings = clone_options.get('clone_payment_settings', True)
        
        clone_talks = clone_options.get('clone_talk_data', True)
        clone_cfp = clone_options.get('clone_cfp', True)
        clone_session_types_tracks = clone_options.get('clone_session_types_tracks', True)
        clone_review_settings = clone_options.get('clone_review_settings', True)

        if clone_common and clone_settings:
            self.plugins = other.plugins
            self.is_public = other.is_public
            self.location = other.location
            self.geo_lat = other.geo_lat
            self.geo_lon = other.geo_lon
            self.currency = other.currency
            
            for extra_link in other.extra_links.all():
                extra_link.pk = None
                extra_link.event = self
                extra_link.save()
                extra_link.log_action('eventyay.object.cloned')

        if other.date_admission:
            self.date_admission = self.date_from + (other.date_admission - other.date_from)
        self.testmode = other.testmode
        self.private_testmode = other.private_testmode
        self.tickets_published = other.tickets_published
        self.talks_published = other.talks_published
        self.save()
        self.log_action('eventyay.object.cloned', data={'source': other.slug, 'source_id': other.pk})

        tax_map = {}
        if clone_ticketing and clone_products:
            for t in other.tax_rules.all():
                tax_map[t.pk] = t
                t.pk = None
                t.event = self
                t.save()
                t.log_action('eventyay.object.cloned')

        category_map = {}
        product_meta_properties_map = {}
        product_map = {}
        variation_map = {}
        question_map = {}
        checkin_list_map = {}
        
        if clone_ticketing:
            if clone_products:
                for c in ProductCategory.objects.filter(event=other):
                    category_map[c.pk] = c
                    c.pk = None
                    c.event = self
                    c.save()
                    c.log_action('eventyay.object.cloned')
    
                for imp in other.product_meta_properties.all():
                    product_meta_properties_map[imp.pk] = imp
                    imp.pk = None
                    imp.event = self
                    imp.save()
                    imp.log_action('eventyay.object.cloned')
    
                for i in Product.objects.filter(event=other).prefetch_related('variations'):
                    vars = list(i.variations.all())
                    product_map[i.pk] = i
                    i.pk = None
                    i.event = self
                    if i.picture:
                        i.picture.save(i.picture.name, i.picture)
                    if i.category_id:
                        i.category = category_map.get(i.category_id)
                    if i.tax_rule_id:
                        i.tax_rule = tax_map.get(i.tax_rule_id)
                    i.save()
                    i.log_action('eventyay.object.cloned')
                    for v in vars:
                        variation_map[v.pk] = v
                        v.pk = None
                        v.product = i
                        v.save()
    
                for imv in ProductMetaValue.objects.filter(product__event=other).prefetch_related('product', 'property'):
                    imv.pk = None
                    imv.property = product_meta_properties_map.get(imv.property.pk)
                    imv.product = product_map.get(imv.product.pk)
                    imv.save()
    
                for ia in ProductAddOn.objects.filter(base_product__event=other).prefetch_related(
                    'base_product', 'addon_category'
                ):
                    ia.pk = None
                    ia.base_product = product_map.get(ia.base_product.pk)
                    ia.addon_category = category_map.get(ia.addon_category.pk)
                    ia.save()
    
                for ia in ProductBundle.objects.filter(base_product__event=other).prefetch_related(
                    'base_product', 'bundled_product', 'bundled_variation'
                ):
                    ia.pk = None
                    ia.base_product = product_map.get(ia.base_product.pk)
                    ia.bundled_product = product_map.get(ia.bundled_product.pk)
                    if ia.bundled_variation:
                        ia.bundled_variation = variation_map.get(ia.bundled_variation.pk)
                    ia.save()
    
                for q in Quota.objects.filter(event=other, subevent__isnull=True).prefetch_related('products', 'variations'):
                    products = list(q.products.all())
                    vars = list(q.variations.all())
                    oldid = q.pk
                    q.pk = None
                    q.event = self
                    q.closed = False
                    q.save()
                    q.log_action('eventyay.object.cloned')
                    for i in products:
                        if i.pk in product_map:
                            q.products.add(product_map[i.pk])
                    for v in vars:
                        if v.pk in variation_map:
                            q.variations.add(variation_map[v.pk])
                    self.products.filter(hidden_if_available_id=oldid).update(hidden_if_available=q)

            if clone_questions:
                for q in Question.objects.filter(event=other).prefetch_related('products', 'options'):
                    products = list(q.products.all())
                    opts = list(q.options.all())
                    question_map[q.pk] = q
                    q.pk = None
                    q.event = self
                    q.save()
                    q.log_action('eventyay.object.cloned')
    
                    for i in products:
                        if i.pk in product_map:
                            q.products.add(product_map[i.pk])
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
                                v[1] = str(product_map.get(int(v[1]), 0).pk) if int(v[1]) in product_map else '0'
                            elif v[0] == 'variation':
                                v[1] = str(variation_map.get(int(v[1]), 0).pk) if int(v[1]) in variation_map else '0'
                        else:
                            _walk_rules(v)
                elif isinstance(rules, list):
                    for i in rules:
                        _walk_rules(i)

            if clone_checkin_lists:
                for cl in other.checkin_lists.filter(subevent__isnull=True).prefetch_related('limit_products'):
                    products = list(cl.limit_products.all())
                    checkin_list_map[cl.pk] = cl
                    cl.pk = None
                    cl.event = self
                    rules = cl.rules
                    _walk_rules(rules)
                    cl.rules = rules
                    cl.save()
                    cl.log_action('eventyay.object.cloned')
                    for i in products:
                        if i.pk in product_map:
                            cl.limit_products.add(product_map[i.pk])
    
                if other.seating_plan:
                    if other.seating_plan.organizer_id == self.organizer_id:
                        self.seating_plan = other.seating_plan
                    else:
                        self.organizer.seating_plans.create(name=other.seating_plan.name, layout=other.seating_plan.layout)
                    self.save()

            for m in other.seat_category_mappings.filter(subevent__isnull=True):
                m.pk = None
                m.event = self
                if m.product_id in product_map:
                    m.product = product_map[m.product_id]
                    m.save()

            for s in other.seats.filter(subevent__isnull=True):
                s.pk = None
                s.event = self
                if s.product_id:
                    s.product = product_map.get(s.product_id)
                s.save()

        skip_settings = (
            'ticket_secrets_eventyay_sig1_pubkey',
            'ticket_secrets_eventyay_sig1_privkey',
            'frontpage_text',
        )
        def is_email_key(k):
            return k.startswith('mail_') or k.startswith('smtp_')
            
        def is_design_key(k):
            return k in (
                'primary_color', 'theme_color_success', 'theme_color_danger', 'theme_color_background', 'theme_round_borders',
                'hover_button_color', 'video_navigation_background_color', 'video_sidebar_text_color', 'video_sidebar_hover_color',
                'primary_font', 'header_background_color', 'header_text_color', 'navigation_text_color', 'menu_text_scroll_over_color',
                'logo_image', 'logo_image_large', 'event_logo_image', 'event_preview_image', 'og_image',
                'banner_text', 'banner_text_bottom', 'header_pattern', 'logo_show_title',
                'menu_label_tickets', 'menu_label_join_video'
            )

        def is_payment_key(k):
            return k.startswith('payment_') or k.startswith('invoice_')

        if clone_common or clone_payment_settings:
            for s in other.settings._objects.all():
                if s.key in skip_settings:
                    continue
                if is_email_key(s.key) and not (clone_common and clone_email_settings):
                    continue
                if is_design_key(s.key) and not (clone_common and clone_design_texts):
                    continue
                if is_payment_key(s.key) and not clone_payment_settings:
                    continue
                if not is_email_key(s.key) and not is_design_key(s.key) and not is_payment_key(s.key) and not (clone_common and clone_settings):
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
            
        if clone_talks:
            from eventyay.base.models.type import SubmissionType
            from eventyay.base.models.track import Track
            from eventyay.base.models.question import TalkQuestion
            from eventyay.base.models.access_code import SubmitterAccessCode
            
            if hasattr(self, 'cfp') and getattr(self.cfp, 'default_type_id', None):
                self.cfp.default_type = None
                self.cfp.save(update_fields=['default_type'])
            
            if clone_session_types_tracks:
                SubmissionType.objects.filter(event=self).delete()
                submission_type_map = {}
                for st in other.submission_types.all():
                    submission_type_map[st.pk] = st
                    st.pk = None
                    st.event = self
                    st.save()
                    st.log_action('eventyay.object.cloned')
    
                track_map = {}
                for tr in other.tracks.all():
                    track_map[tr.pk] = tr
                    tr.pk = None
                    tr.event = self
                    tr.save()
                    tr.log_action('eventyay.object.cloned')
                
                talk_question_map = {}
                talk_question_deps = {}
                for tq in other.talkquestions.prefetch_related('options', 'tracks', 'submission_types'):
                    tq_tracks = list(tq.tracks.all())
                    tq_submission_types = list(tq.submission_types.all())
                    tq_options = list(tq.options.all())
                    old_dep_id = tq.dependency_question_id
                    
                    talk_question_map[tq.pk] = tq
                    tq.pk = None
                    tq.event = self
                    tq.dependency_question = None
                    tq.save()
                    tq.log_action('eventyay.object.cloned')
                    
                    if old_dep_id:
                        talk_question_deps[tq] = old_dep_id
                    
                    for o in tq_options:
                        o.pk = None
                        o.question = tq
                        o.save()
                    for tr in tq_tracks:
                        tq.tracks.add(track_map[tr.pk])
                    for st in tq_submission_types:
                        tq.submission_types.add(submission_type_map[st.pk])
                        
                for tq, old_dep_id in talk_question_deps.items():
                    tq.dependency_question = talk_question_map.get(old_dep_id)
                    if tq.dependency_question:
                        tq.save(update_fields=['dependency_question'])
                
                if hasattr(self, 'cfp') and hasattr(other, 'cfp') and getattr(other.cfp, 'default_type_id', None):
                    self.cfp.default_type = submission_type_map.get(other.cfp.default_type_id)
                    self.cfp.save(update_fields=['default_type'])
                    
                for ac in other.submitter_access_codes.all():
                    ac.pk = None
                    ac.event = self
                    if ac.track_id:
                        ac.track = track_map.get(ac.track_id)
                    if ac.submission_type_id:
                        ac.submission_type = submission_type_map.get(ac.submission_type_id)
                    ac.save()
                    ac.log_action('eventyay.object.cloned')

            if clone_review_settings:
                from eventyay.base.models import ReviewPhase, ReviewScoreCategory, ReviewScore

                self.review_phases.all().delete()
                for rp in other.review_phases.all():
                    rp.pk = None
                    rp.event = self
                    rp.save()
                    rp.log_action('eventyay.object.cloned')

                self.score_categories.all().delete()
                for sc in other.score_categories.prefetch_related('scores'):
                    scores = list(sc.scores.all())
                    sc.pk = None
                    sc.event = self
                    sc.save()
                    sc.log_action('eventyay.object.cloned')
                    for score in scores:
                        score.pk = None
                        score.category = sc
                        score.save()
        
        event_copy_data.send(
            sender=self,
            other=other,
            tax_map=tax_map,
            category_map=category_map,
            product_map=product_map,
            variation_map=variation_map,
            question_map=question_map,
            checkin_list_map=checkin_list_map,
            clone_options=clone_options,
        )

    def decode_token(self, token, allow_raise=False):
        exc = None
        tried_any = False
        for jwt_config in (self.config or {}).get('JWT_secrets', []):
            tried_any = True
            secret = jwt_config['secret']
            audience = jwt_config['audience']
            issuer = jwt_config['issuer']
            try:
                return jwt.decode(
                    token,
                    secret,
                    algorithms=['HS256'],
                    audience=audience,
                    issuer=issuer,
                )
            except jwt.exceptions.ExpiredSignatureError:
                if allow_raise:
                    raise
            except jwt.exceptions.InvalidTokenError as e:
                exc = e
        # Fallback to event settings used by the ticket-video plugin if no JWT_secrets configured
        if not tried_any:
            issuer = getattr(self.settings, 'venueless_issuer', None)
            audience = getattr(self.settings, 'venueless_audience', None)
            secret = getattr(self.settings, 'venueless_secret', None)
            if issuer and audience and secret:
                try:
                    return jwt.decode(
                        token,
                        secret,
                        algorithms=['HS256'],
                        audience=audience,
                        issuer=issuer,
                    )
                except jwt.exceptions.ExpiredSignatureError:
                    if allow_raise:
                        raise
                except jwt.exceptions.InvalidTokenError as e:
                    exc = e
        if allow_raise:
            if exc:
                raise exc
            raise jwt.exceptions.InvalidTokenError('No JWT secrets configured')

    def _get_trait_grants_with_defaults(self):
        base_trait_grants = self.trait_grants if self.trait_grants is not None else default_grants()
        slug = getattr(self, 'slug', None) or getattr(self, 'id', None)
        if not slug:
            return base_trait_grants
        augmented = dict(base_trait_grants)
        augmented['attendee'] = resolve_attendee_trait_grant(
            self, augmented.get('attendee', ['attendee'])
        )
        for role, trait_name in VIDEO_TRAIT_ROLE_MAP.items():
            augmented.setdefault(role, [f'eventyay-video-event-{slug}-{trait_name.replace("_", "-")}'])
        return augmented

    def _get_default_roles(self):
        """Return ``default_roles()``, cached on this Event for its instance lifetime."""
        cached = getattr(self, '_cached_default_roles', None)
        if cached is None:
            cached = default_roles()
            self._cached_default_roles = cached
        return cached

    def _permissions_for_role(self, role_name, event_roles=None):
        """
        Resolve a role's permission list.

        Prefer the event's stored ``roles`` JSON, then ``default_roles()`` (includes
        ``admin`` / attendee stacks), then ``SYSTEM_ROLES`` for built-in video roles.
        Using only ``SYSTEM_ROLES`` as fallback wrongly drops ``admin`` because that
        role is not defined there.
        """
        if event_roles is None:
            event_roles = self.roles if self.roles is not None else {}
        if role_name in event_roles and event_roles[role_name] is not None:
            return event_roles[role_name]
        defaults = self._get_default_roles()
        if role_name in defaults:
            return defaults[role_name]
        return SYSTEM_ROLES.get(role_name, [])

    def has_permission_implicit(
        self,
        *,
        traits,
        permissions: list[Permission],
        room=None,
        allow_empty_traits=True,
    ):
        event_trait_grants = self._get_trait_grants_with_defaults()
        event_roles = self.roles if self.roles is not None else self._get_default_roles()

        if traits is None:
            traits = []

        admin_mode_active = 'admin' in traits
        if admin_mode_active:
            for role_name in ORGANIZER_ROLES:
                role_permissions = self._permissions_for_role(role_name, event_roles)
                role_permissions_str = [normalize_permission_value(rp) for rp in role_permissions]
                if any(normalize_permission_value(p) in role_permissions_str for p in permissions):
                    return True

        attendee_traits = event_trait_grants.get('attendee', ['attendee'])
        if traits_match_required(traits, attendee_traits) and (attendee_traits or allow_empty_traits):
            role_permissions = self._permissions_for_role('attendee', event_roles)
            role_permissions_str = [normalize_permission_value(rp) for rp in role_permissions]
            role_permissions_str.append(normalize_permission_value(Permission.EVENT_CHAT_DIRECT))
            if any(normalize_permission_value(p) in role_permissions_str for p in permissions):
                return True

        for role, required_traits in event_trait_grants.items():
            if role == 'attendee':
                continue
            if role in ORGANIZER_ROLES:
                if not required_traits or not traits_match_required(traits, required_traits):
                    continue
            else:
                if not (traits_match_required(traits, required_traits) and (required_traits or allow_empty_traits)):
                    continue
            role_permissions = self._permissions_for_role(role, event_roles)
            role_permissions_str = [normalize_permission_value(rp) for rp in role_permissions]
            if any(normalize_permission_value(p) in role_permissions_str for p in permissions):
                return True

        if room:
            room_trait_grants = room.trait_grants if room.trait_grants is not None else {}
            for role, required_traits in room_trait_grants.items():
                if role in ORGANIZER_ROLES:
                    if not required_traits or not traits_match_required(traits, required_traits):
                        continue
                else:
                    if not (traits_match_required(traits, required_traits) and (required_traits or allow_empty_traits)):
                        continue
                role_permissions = self._permissions_for_role(role, event_roles)
                role_permissions_str = [normalize_permission_value(rp) for rp in role_permissions]
                if any(normalize_permission_value(p) in role_permissions_str for p in permissions):
                    return True

        # Return False if no permission was granted
        return False

    def has_organizer_role_implicit(self, *, traits, room=None):
        event_trait_grants = self._get_trait_grants_with_defaults()

        if traits is None:
            traits = []

        if 'admin' in traits:
            return True

        for role, required_traits in event_trait_grants.items():
            if (
                role in ORGANIZER_ROLES
                and traits_match_required(traits, required_traits)
                and required_traits
            ):
                return True

        if room:
            room_trait_grants = room.trait_grants if room.trait_grants is not None else {}
            for role, required_traits in room_trait_grants.items():
                if (
                    role in ORGANIZER_ROLES
                    and traits_match_required(traits, required_traits)
                    and required_traits
                ):
                    return True

        return False

    def has_organizer_role(self, *, user, room=None):
        if user.is_banned:  # pragma: no cover
            return False

        if self.has_organizer_role_implicit(
            traits=user.traits or [],
            room=room,
        ):
            return True

        return bool(ORGANIZER_ROLES.intersection(user.get_role_grants(room)))

    async def has_organizer_role_async(self, *, user, room=None):
        if user.is_banned:  # pragma: no cover
            return False

        if self.has_organizer_role_implicit(
            traits=user.traits or [],
            room=room,
        ):
            return True

        roles = await user.get_role_grants_async(room)
        return bool(ORGANIZER_ROLES.intersection(roles))

    def has_permission(self, *, user, permission: Permission, room=None):
        """
        Returns whether a user holds a given permission either on the world or on a specific room.
        ``permission`` can be one ``Permission`` or a list of these, in which case it will perform an OR lookup.
        """
        if user.is_banned:  # pragma: no cover
            # safeguard only
            return False

        if not isinstance(permission, list):
            permission = [permission]

        if user.is_silenced and not any(p in MAX_PERMISSIONS_IF_SILENCED for p in permission):
            return False

        if self.has_permission_implicit(
            traits=user.traits or [],
            permissions=permission,
            room=room,
            allow_empty_traits=user.type == User.UserType.PERSON,
        ):
            return True

        roles = user.get_role_grants(room)
        event_roles = self.roles if self.roles is not None else self._get_default_roles()
        for r in roles:
            role_perms = self._permissions_for_role(r, event_roles)
            role_perms_str = [normalize_permission_value(rp) for rp in role_perms]
            if any(normalize_permission_value(p) in role_perms_str for p in permission):
                return True
        return False

    async def has_permission_async(self, *, user, permission: Permission, room=None):
        """
        Returns whether a user holds a given permission either on the world or on a specific room.
        ``permission`` can be one ``Permission`` or a list of these, in which case it will perform an OR lookup.
        """
        if user.is_banned:  # pragma: no cover
            # safeguard only
            return False

        if not isinstance(permission, list):
            permission = [permission]

        if user.is_silenced and not any(p in MAX_PERMISSIONS_IF_SILENCED for p in permission):
            return False

        if self.has_permission_implicit(
            traits=user.traits or [],
            permissions=permission,
            room=room,
            allow_empty_traits=user.type == User.UserType.PERSON,
        ):
            return True

        roles = await user.get_role_grants_async(room)
        event_roles = self.roles if self.roles is not None else self._get_default_roles()
        for r in roles:
            role_perms = self._permissions_for_role(r, event_roles)
            role_perms_str = [normalize_permission_value(rp) for rp in role_perms]
            if any(normalize_permission_value(p) in role_perms_str for p in permission):
                return True
        return False

    def get_all_permissions(self, user):
        result = defaultdict(set)
        if user.is_banned:  # pragma: no cover
            return result

        allow_empty_traits = user.type == User.UserType.PERSON

        # Ensure trait_grants and roles are not None
        event_trait_grants = self._get_trait_grants_with_defaults()
        event_roles = self.roles if self.roles is not None else self._get_default_roles()

        user_traits = user.traits or []

        for role, required_traits in event_trait_grants.items():
            if role in ORGANIZER_ROLES:
                if not required_traits or not traits_match_required(user_traits, required_traits):
                    continue
            else:
                if not (traits_match_required(user_traits, required_traits) and (required_traits or allow_empty_traits)):
                    continue
            result[self].update(self._permissions_for_role(role, event_roles))

        # Admin mode in the ticket/talk system is represented by the ``admin`` trait on the video side.
        # When admin mode is ON, the user has the ``admin`` trait and should retain full access.
        admin_mode_active = 'admin' in user_traits

        if admin_mode_active:
            # Grant all video manager permissions when admin mode is active
            for role_name in ORGANIZER_ROLES:
                result[self].update(self._permissions_for_role(role_name, event_roles))

        attendee_traits = event_trait_grants.get('attendee', ['attendee'])
        if traits_match_required(user_traits, attendee_traits) and (attendee_traits or allow_empty_traits):
            result[self].add(Permission.EVENT_CHAT_DIRECT)

        for room in self.rooms.all():
            room_trait_grants = room.trait_grants if room.trait_grants is not None else {}
            for role, required_traits in room_trait_grants.items():
                if role in ORGANIZER_ROLES:
                    if not required_traits or not traits_match_required(user_traits, required_traits):
                        continue
                else:
                    if not (traits_match_required(user_traits, required_traits) and (required_traits or allow_empty_traits)):
                        continue
                result[room].update(self._permissions_for_role(role, event_roles))

        for grant in user.room_grants.select_related('room'):
            result[grant.room].update(self._permissions_for_role(grant.role, event_roles))
        if user.is_silenced:
            for key in result.keys():
                result[key] &= MAX_PERMISSIONS_IF_SILENCED

        return result

    def clear_data(self):
        """
        Clears all personal information. It generally leaves structure such as rooms intact, but to make
        sure all personal data is scrubbed, it also clears all uploaded files.
        """
        from eventyay.base.models import (
            ChatEvent,
            Membership,
            Poll,
            Reaction,
            RoomView,
        )
        from eventyay.base.models.storage_model import StoredFile

        self.audit_logs.all().delete()
        self.event_grants.all().delete()
        self.room_grants.all().delete()
        self.bbb_calls.all().delete()
        ChatEvent.objects.filter(channel__event=self).delete()
        Membership.objects.filter(channel__event=self).delete()
        Reaction.objects.filter(room__event=self).delete()
        RoomView.objects.filter(room__event=self).delete()
        EventView.objects.filter(event=self).delete()
        RoomQuestion.objects.filter(room__event=self).delete()
        Poll.objects.filter(room__event=self).delete()
        SystemLog.objects.filter(event=self).delete()
        for f in StoredFile.objects.filter(event=self):
            f.full_delete()

        self.user_set.all().delete()
        self.domain = None
        self.save()

    def clone_from(self, old, new_secrets):
        from eventyay.base.models import Channel
        from eventyay.base.models.storage_model import StoredFile

        if self.pk == old.pk:
            raise ValueError('Illegal attempt to clone into same event')
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
                    # probably external or something we don't understand
                    return url
            elif isinstance(struct, str):
                return clone_stored_files(url=struct)
            elif isinstance(struct, dict):
                return {k: clone_stored_files(struct=v) for k, v in struct.items()}
            elif isinstance(struct, (list, tuple)):
                return [clone_stored_files(struct=e) for e in struct]
            else:
                return struct

        self.config = old.config or {}
        if new_secrets:
            secret = get_random_string(length=64)
            self.config['JWT_secrets'] = [
                {
                    'issuer': 'any',
                    'audience': 'eventyay',
                    'secret': secret,
                }
            ]
        self.roles = old.roles
        self.trait_grants = old.trait_grants
        self.locale = old.locale
        self.timezone = old.timezone
        self.feature_flags = old.feature_flags
        self.external_auth_url = old.external_auth_url
        self.save()

        for r in old.rooms.all():
            try:
                has_channel = r.channel
            except Exception:
                has_channel = False

            r.pk = None
            r.event = self
            r.module_config = clone_stored_files(struct=r.module_config)
            r.save()
            if has_channel:
                Channel.objects.create(room=r, event=self)

    def get_payment_providers(self, cached=False) -> dict:
        """
        Returns a dictionary of initialized payment providers mapped by their identifiers.
        """
        from ..signals import register_payment_providers
        from ..meetup import is_meetup_event

        if not cached or not hasattr(self, '_cached_payment_providers'):
            responses = register_payment_providers.send(self)
            providers = {}
            is_meetup = is_meetup_event(self)
            for receiver, response in responses:
                if not isinstance(response, list):
                    response = [response]
                for p in response:
                    pp = p(self)
                    if is_meetup and pp.identifier == 'stripe_settings':
                        continue
                    if not is_meetup and pp.identifier == 'stripe' and p.__module__ == 'eventyay.base.payment':
                        continue
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
            has_paid_product=Value(
                self.cache.get_or_set(
                    'has_paid_product',
                    lambda: self.products.filter(default_price__gt=0).exists(),
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
    def talks_testmode(self):
        return self.settings.get('talks_testmode', False, as_type=bool)

    @property
    def private_testmode_tickets_enabled(self):
        return self.private_testmode and self.settings.get('private_testmode_tickets', True, as_type=bool)

    @property
    def private_testmode_talks_enabled(self):
        return self.private_testmode and self.settings.get('private_testmode_talks', False, as_type=bool)

    def _component_presale_status(self, *, published: bool, private_testmode_enabled: bool, testmode: bool):
        if private_testmode_enabled:
            text = _('live (private test mode)') if self.live else _('in private test mode')
        elif self.live and testmode:
            text = _('live and in test mode')
        elif self.live and published:
            text = _('live')
        elif testmode:
            text = _('in test mode')
        else:
            text = _('not yet public')

        is_live = bool(self.live and (published or private_testmode_enabled or testmode))
        is_plain_live = bool(self.live and published and not private_testmode_enabled and not testmode)
        return {
            'class': 'live' if is_live else 'off',
            'icon': 'fa-check-circle' if is_plain_live else ('fa-warning' if is_live else 'fa-times-circle'),
            'is_live': is_live,
            'text': text,
            'text_class': 'text-success' if is_live else 'text-danger',
        }

    @property
    def ticket_component_presale_status(self):
        return self._component_presale_status(
            published=self.tickets_published,
            private_testmode_enabled=self.private_testmode_tickets_enabled,
            testmode=self.testmode,
        )

    @property
    def talk_component_presale_status(self):
        return self._component_presale_status(
            published=self.talks_published,
            private_testmode_enabled=self.private_testmode_talks_enabled,
            testmode=self.talks_testmode,
        )

    @property
    def organiser(self):
        """British spelling alias used throughout Talk code and tests."""
        return self.organizer

    @organiser.setter
    def organiser(self, value):
        self.organizer = value

    @property
    def has_component_testmode(self):
        return bool(self.testmode or self.talks_testmode)

    def user_can_view_tickets(self, user=None, request=None):
        private_tickets = self.private_testmode_tickets_enabled
        if not self.tickets_published and not private_tickets:
            return False
        if not private_tickets:
            return True
        if not user or not getattr(user, 'is_authenticated', False):
            return False
        if getattr(user, 'is_administrator', False):
            return True
        return user.has_event_permission(self.organizer, self, request=request)

    def contact_form_recipient_email(self):
        return self.settings.contact_mail or self.email or ''

    def show_contact_form(self):
        if not self.contact_form_recipient_email():
            return False
        if not self.settings._objects.filter(key='contact_form_enabled').exists():
            return True
        raw = self.settings.get('contact_form_enabled', as_type=str)
        if raw in ('False', 'false', '0'):
            return False
        if raw in ('True', 'true', '1'):
            return True
        return True

    def user_can_view_talks(self, user=None, request=None):
        private_talks = self.private_testmode_talks_enabled
        if not self.talks_published and not private_talks:
            return False
        if not private_talks:
            return True
        if not user or not getattr(user, 'is_authenticated', False):
            return False
        if getattr(user, 'is_administrator', False):
            return True
        return user.has_event_permission(self.organizer, self, request=request)

    @property
    def has_paid_things(self):
        from .product import Product, ProductVariation

        return (
            Product.objects.filter(event=self, default_price__gt=0).exists()
            or ProductVariation.objects.filter(product__event=self, default_price__gt=0).exists()
        )

    @property
    def talk_schedule_url(self):
        return self.urls.schedule

    @property
    def talk_session_url(self):
        return self.urls.talks

    @property
    def talk_speaker_url(self):
        return self.urls.speakers

    @property
    def talk_dashboard_url(self):
        return reverse('orga:event.dashboard', kwargs={'organizer': self.organizer.slug, 'event': self.slug})

    @property
    def talk_settings_url(self):
        return reverse('orga:settings.event.view', kwargs={'organizer': self.organizer.slug, 'event': self.slug})

    @cached_property
    def live_issues(self):
        from eventyay.base.signals import event_live_issues

        issues = []

        if self.has_paid_things and not self.has_payment_provider:
            issues.append(_('You have configured at least one paid product but have not enabled any payment methods.'))

        if self.products.exists() and not self.quotas.exists():
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

        issues.extend(self.billing_issues())

        responses = event_live_issues.send(self)
        for receiver, response in sorted(responses, key=lambda r: str(r[0])):
            if response:
                issues.append(response)

        return issues

    def billing_issues(self):
        from django.utils.translation import gettext

        from eventyay.base.models.organizer import OrganizerBillingModel
        from eventyay.base.settings import GlobalSettingsObject

        issues = []
        gs = GlobalSettingsObject()
        billing_validation_enabled = gs.settings.get('billing_validation', as_type=bool, default=True)
        if not billing_validation_enabled:
            return issues

        billing_obj = OrganizerBillingModel.objects.filter(organizer=self.organizer).first()
        if not billing_obj or not billing_obj.stripe_payment_method_id:
            url = reverse(
                'eventyay_common:organizer.billing',
                kwargs={'organizer': self.organizer.slug},
            )
            issue = format_html(
                '<a href="{}#tab-0-1-open">{}</a>',
                url,
                gettext('You need to fill the billing information.'),
            )
            issues.append(issue)
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

    @scopes_disabled()
    def delete_sub_objects(self):
        from django.core.exceptions import ObjectDoesNotExist

        from eventyay.base.models.auth import EventGrant, RoomGrant, ShortToken, User
        from eventyay.base.models.feedback import Feedback
        from eventyay.base.models.log import ActivityLog, LogEntry
        from eventyay.base.models.mail import QueuedMail
        from eventyay.base.models.question import Answer, AnswerOption
        from eventyay.base.models.resource import Resource
        from eventyay.base.models.slot import TalkSlot
        from eventyay.base.models.storage_model import StoredFile
        from eventyay.base.models.systemlog import SystemLog

        self.cartposition_set.filter(addon_to__isnull=False).delete()
        self.cartposition_set.all().delete()
        self.queued_mails.all().delete()

        answers = Answer.objects.filter(question__event=self)
        for answer in answers.only('pk', 'answer_file').iterator():
            answer._delete_files()
        answers.delete()
        AnswerOption.objects.filter(question__event=self).delete()

        TalkSlot.objects.filter(schedule__event=self).delete()
        Feedback.objects.filter(talk__event=self).delete()

        resources = Resource.objects.filter(submission__event=self)
        for resource in resources.only('pk', 'resource').iterator():
            resource._delete_files()
        resources.delete()

        for domain in self.domains.all().iterator():
            domain.delete()

        for stored_file in StoredFile.objects.filter(event=self).iterator():
            stored_file.full_delete()

        self.bbbserver_set.update(event_exclusive=None)
        self.janusserver_set.update(event_exclusive=None)
        self.jitsiserver_set.update(event_exclusive=None)
        self.turnserver_set.update(event_exclusive=None)

        self.vouchers.all().delete()
        self.products.all().delete()
        self.subevents.all().delete()
        self.talkquestions.all().delete()
        self.submissions.all().delete()
        self.rooms.all().delete()
        self.tracks.all().delete()
        self.tags.all().delete()
        self.schedules.all().delete()
        mail_templates = self.mail_templates.all()
        QueuedMail.objects.filter(template__in=mail_templates).update(template=None)
        mail_templates.delete()
        ActivityLog.objects.filter(event=self).delete()
        LogEntry.all.filter(event=self).update(event=None)
        SystemLog.objects.filter(event=self).update(event=None)
        EventGrant.objects.filter(event=self).delete()
        RoomGrant.objects.filter(event=self).delete()
        ShortToken.objects.filter(event=self).delete()
        User.objects.filter(event=self).delete()
        EventView.objects.filter(event=self).delete()
        self.audits.all().delete()
        self.meta_values.all().delete()
        self.extra_links.all().delete()
        self.planned_usages.all().delete()
        self.requiredaction_set.all().delete()
        self.settings.flush()
        try:
            cfp = self.cfp
        except ObjectDoesNotExist:
            cfp = None
        if cfp is not None and cfp.pk is not None:
            cfp.delete()
        self.submitter_access_codes.all().delete()
        self.submission_types.all().delete()

    @scopes_disabled()
    @transaction.atomic
    def delete_talk_data(self):
        from django.core.exceptions import ObjectDoesNotExist

        from eventyay.base.models.mail import QueuedMail
        from eventyay.base.models.profile import SpeakerProfile
        from eventyay.base.models.feedback import Feedback
        from eventyay.base.models.question import Answer, AnswerOption
        from eventyay.base.models.resource import Resource
        from eventyay.base.models.slot import TalkSlot

        answers = Answer.objects.filter(question__event=self)
        for answer in answers.only('pk', 'answer_file').iterator():
            try:
                answer._delete_files()
            except Exception:
                logger.error("Failed to delete files for Answer %s", answer.pk, exc_info=True)
        answers.delete()
        AnswerOption.objects.filter(question__event=self).delete()

        TalkSlot.objects.filter(schedule__event=self).delete()
        Feedback.objects.filter(talk__event=self).delete()

        resources = Resource.objects.filter(submission__event=self)
        for resource in resources.only('pk', 'resource').iterator():
            try:
                resource._delete_files()
            except Exception:
                logger.error("Failed to delete files for Resource %s", resource.pk, exc_info=True)
        resources.delete()

        SpeakerProfile.objects.filter(event=self).delete()

        # Clear unsent (outbox) emails linked to this event
        QueuedMail.objects.filter(event=self, sent__isnull=True).delete()

        self.talkquestions.all().delete()
        self.submissions.all().delete()
        self.rooms.all().delete()
        self.tracks.all().delete()
        self.tags.all().delete()
        self.schedules.all().delete()
        try:
            cfp = self.cfp
        except ObjectDoesNotExist:
            cfp = None
        if cfp is not None and cfp.pk is not None:
            cfp.delete()
            try:
                del self.__dict__['cfp']
            except KeyError:
                pass
        self.submitter_access_codes.all().delete()
        self.submission_types.all().delete()
        self.score_categories.all().delete()
        self.review_phases.all().delete()
        self.build_initial_data()

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

    # From eventyay-talk

    @cached_property
    def locales(self) -> list[str]:
        """Is a list of active event locales."""
        try:
            if hasattr(self, 'settings') and 'locales' in self.settings._cache():
                if locales := self.settings.get('locales', as_type=list):
                    return locales
        except RedisError:
            logger.warning('Event settings cache unavailable while reading locales for %s', self.slug)
        return [code for code in self.locale_array.split(',') if code]

    @cached_property
    def content_locales(self) -> list[str]:
        """Is a list of active content locales."""
        try:
            if hasattr(self, 'settings') and 'content_locales' in self.settings._cache():
                if locales := self.settings.get('content_locales', as_type=list):
                    return locales
        except RedisError:
            logger.warning('Event settings cache unavailable while reading content locales for %s', self.slug)
        fallback = [code for code in self.content_locale_array.split(',') if code]
        return fallback or self.locales

    def _clear_language_caches(self):
        for attr in [
            'locales',
            'content_locales',
            'is_multilingual',
            'named_locales',
            'available_content_locales',
            'named_content_locales',
            'named_plugin_locales',
            'plugin_locales',
        ]:
            self.__dict__.pop(attr, None)

    def update_language_configuration(
        self,
        *,
        locales: list[str] | None = None,
        content_locales: list[str] | None = None,
        default_locale: str | None = None,
    ) -> None:

        locales_list = list(locales or [])

        if locales_list:
            self.locale_array = ','.join(locales_list)
            self.settings.set('locales', locales_list)
        if default_locale:
            self.locale = default_locale
            self.settings.set('locale', default_locale)

        if content_locales is not None:
            content_locales_list = list(content_locales)
            self.content_locale_array = ','.join(content_locales_list)
            self.settings.set('content_locales', content_locales_list)
        if locales_list or content_locales is not None or default_locale:
            self.save()
            self._clear_language_caches()

    @cached_property
    def is_multilingual(self) -> bool:
        """Is ``True`` if the event supports more than one locale."""
        return len(self.locales) > 1

    @cached_property
    def named_locales(self) -> list:
        """Is a list of tuples of locale codes and natural names for this
        event."""
        return [
            (code, language['natural_name'])
            for code, language in settings.LANGUAGES_INFORMATION.items()
            if code in self.locales
        ]

    @cached_property
    def available_content_locales(self) -> list:
        # Content locales can be anything eventyay knows as a language, merged with
        # this event's plugin locales.

        locale_names = dict(settings.LANGUAGES)
        locale_names.update(self.named_plugin_locales)
        return sorted([(key, value) for key, value in locale_names.items()])

    @cached_property
    def named_content_locales(self) -> list:
        locale_names = dict(self.available_content_locales)
        # locale_names['en-us'] = locale_names['en']
        locale_names |= LANGUAGE_NAMES
        return [(code, locale_names.get(code, code)) for code in self.content_locales]

    @cached_property
    def named_plugin_locales(self) -> list:
        from eventyay.common.signals import register_locales

        locale_names = copy.copy(LANGUAGE_NAMES)
        locale_names.update(self.named_locales)
        result = {}
        for _receiver, locales in register_locales.send(sender=self):
            for locale in locales:
                if isinstance(locale, tuple):
                    result[locale[0]] = locale[1]
                else:
                    result[locale] = locale_names.get(locale, locale)
        return result

    @cached_property
    def plugin_locales(self) -> list:
        return sorted(self.named_plugin_locales.keys())

    @property
    def plugin_list(self) -> list:
        if not self.plugins:
            return []
        return self.plugins.split(',')

    @cached_property
    def available_plugins(self):
        return {
            plugin.module: plugin
            for plugin in get_all_plugins(self)
            if not plugin.name.startswith('.') and getattr(plugin, 'visible', True)
        }

    def set_plugins(self, modules: list) -> None:
        """
        This method is not @plugin_list.setter to make the side effects more visible.
        It will call installed() on all plugins that were not active before, and
        uninstalled() on all plugins that are not active anymore.
        """
        plugins_active = set(self.plugin_list)

        enable = set(modules) & (set(self.available_plugins) - plugins_active)
        disable = plugins_active - set(modules)

        for module in enable:
            if hasattr(self.available_plugins[module].app, 'installed'):
                self.available_plugins[module].app.installed(self)
        for module in disable:
            if hasattr(self.available_plugins[module].app, 'uninstalled'):
                self.available_plugins[module].app.uninstalled(self)

        self.plugins = ','.join(modules)

    @property
    def visible_primary_color(self):
        """
        Prefer the common (event settings) primary color, then fall back to the legacy
        event field, finally defaulting to the installation default.
        """
        return self.settings.get('primary_color') or self.primary_color or settings.DEFAULT_EVENT_PRIMARY_COLOR

    @cached_property
    def _visible_logo_path(self):
        """
        Resolve a usable logo path/URL from event_logo_image setting.
        Returns a storage-relative path (e.g. ``pub/...``) or an absolute URL.

        NOTE: This method ONLY checks for event_logo_image, NOT logo_image.
        The logo_image setting is actually used for HEADER images (see default_setting.py),
        so we must NOT use it here to prevent header images from appearing as logos.
        """
        # Only check event_logo_image - NOT logo_image (which is for header images)
        raw = self.settings.get('event_logo_image', as_type=str, default=None)
        return _resolve_media_path(raw)

    @cached_property
    def _visible_header_image_path(self):
        """
        Resolve a usable header image path/URL from common settings, falling back to the legacy field.

        The header image is stored under ``logo_image`` for historical reasons; ``header_image`` is
        the legacy model field.
        """
        # Prefer settings key first (historical name), then legacy model field
        for key in ('logo_image', 'header_image'):
            raw = self.settings.get(key, as_type=str, default=None)
            path = _resolve_media_path(raw)
            if path:
                return path

        if self.header_image:
            return self.header_image.name

        return None

    @cached_property
    def _visible_preview_image_path(self):
        """
        Resolve a usable preview image path/URL from the ``event_preview_image`` setting.
        Returns a storage-relative path (e.g. ``pub/…``) or an absolute HTTP URL.
        """
        raw = self.settings.get('event_preview_image', as_type=str, default=None)
        return _resolve_media_path(raw)

    @cached_property
    def visible_preview_image_url(self):
        from django.core.files.storage import default_storage

        if not self._visible_preview_image_path:
            return None
        with suppress(Exception):
            if is_http_url(str(self._visible_preview_image_path)):
                return self._visible_preview_image_path
            return default_storage.url(self._visible_preview_image_path)
        return None

    @cached_property
    def preview_image_url_with_fallback(self):
        """
        Return the resolved URL of the preview image, falling back to header image, then logo.
        If none of these are set, it returns None (which the start page card template handles by
        rendering a default calendar placeholder icon).

        For local (non-HTTP) paths, a thumbnail is generated at 800×450 with a fill-crop (``^``).
        ``get_thumbnail`` caches results on disk using a deterministic key derived from the path
        and geometry, so repeated calls for the same image are cheap (file-existence check only).
        This method itself is a ``@cached_property``, so it is only invoked once per ``Event``
        instance per request — no thundering-herd risk within a single request.
        """
        path = self._visible_preview_image_path or self._visible_header_image_path or self._visible_logo_path
        if not path:
            return None

        if is_http_url(str(path)):
            return path

        try:
            return get_thumbnail(path, '800x450^').thumb.url
        except Exception:
            logger.exception('Failed to create preview thumbnail for path: %s', path)
            try:
                return default_storage.url(path)
            except Exception:
                return None

    @cached_property
    def preview_image_url_small(self):
        """
        Return a smaller 400×225 resolved URL of the preview image for responsive srcset delivery.
        """
        path = self._visible_preview_image_path or self._visible_header_image_path or self._visible_logo_path
        if not path:
            return None

        if is_http_url(str(path)):
            return path

        try:
            return get_thumbnail(path, '400x225^').thumb.url
        except Exception:
            return self.preview_image_url_with_fallback

    @cached_property
    def visible_logo_url(self):
        from django.core.files.storage import default_storage

        if not self._visible_logo_path:
            return None
        with suppress(Exception):
            # If already a full URL, return as-is
            if is_http_url(str(self._visible_logo_path)):
                return self._visible_logo_path
            return default_storage.url(self._visible_logo_path)
        return None

    @cached_property
    def visible_logo_file(self):
        from django.core.files.storage import default_storage

        if not self._visible_logo_path:
            return None
        with suppress(Exception):
            if is_http_url(str(self._visible_logo_path)):
                return None
            return default_storage.open(self._visible_logo_path)

    @cached_property
    def visible_header_image_url(self):
        from django.core.files.storage import default_storage

        if not self._visible_header_image_path:
            return None
        with suppress(Exception):
            if is_http_url(str(self._visible_header_image_path)):
                return self._visible_header_image_path
            return default_storage.url(self._visible_header_image_path)

    @cached_property
    def visible_header_image_file(self):
        from django.core.files.storage import default_storage

        if not self._visible_header_image_path:
            return None
        with suppress(Exception):
            if is_http_url(str(self._visible_header_image_path)):
                return None
            return default_storage.open(self._visible_header_image_path)
        return None

    def _get_default_submission_type(self):
        from eventyay.base.models import SubmissionType

        with scope(event=self):
            sub_type = SubmissionType.objects.filter(event=self).first()
            if not sub_type:
                sub_type = SubmissionType.objects.create(event=self, name='Talk')
        return sub_type

    @cached_property
    def event(self):
        return self

    def feature_flags_as_mapping(self):
        flags = self.feature_flags or {}
        if isinstance(flags, dict):
            return flags
        if isinstance(flags, (list, tuple, set)):
            return {flag: True for flag in flags if isinstance(flag, str)}
        return {}

    def get_feature_flag(self, feature):
        flags = self.feature_flags_as_mapping()
        if feature in flags:
            return flags[feature]
        return default_feature_flags().get(feature, False)

    def session_popularity_show_on_schedule(self):
        flags = self.feature_flags_as_mapping()
        if 'session_popularity_show_on_schedule' in flags:
            return bool(flags['session_popularity_show_on_schedule'])
        return bool(
            flags.get('session_popularity_show_on_calendar', True)
            or flags.get('session_popularity_show_on_list', True)
        )

    def schedule_client_feature_flags(self):
        """Feature flags exposed to schedule webapp clients via inline JSON."""
        from eventyay.talk_rules.submission import are_featured_speakers_visible

        popularity_enabled = bool(self.get_feature_flag('session_popularity_enabled'))
        return {
            'session_popularity_enabled': popularity_enabled,
            'session_popularity_show_on_schedule': self.session_popularity_show_on_schedule(),
            'featured_speakers_enabled': are_featured_speakers_visible(None, self),
        }

    @cached_property
    def duration(self):
        return (self.date_to - self.date_from).days + 1

    @cached_property
    def reviews(self):
        from eventyay.base.models import Review

        return Review.objects.filter(submission__event=self)

    @cached_property
    def datetime_from(self) -> dt.datetime:
        """The localised datetime of the event start date.

        :rtype: datetime.datetime
        """
        return make_aware(
            dt.datetime.combine(self.date_from, dt.time(hour=0, minute=0, second=0)),
            self.tz,
        )

    @cached_property
    def datetime_to(self) -> dt.datetime:
        """The localised datetime of the event end date.

        :rtype: datetime.datetime
        """
        return make_aware(
            dt.datetime.combine(self.date_to, dt.time(hour=23, minute=59, second=59)),
            self.tz,
        )

    @cached_property
    def tz(self):
        return ZoneInfo(self.timezone)

    @cached_property
    def talks(self):
        """Returns a queryset of all.

        :class:`~eventyay.base.models.submission.Submission` object in the
        current released schedule.
        """
        from eventyay.base.models import Submission

        if self.current_schedule:
            return (
                self.submissions.filter(slots__in=self.current_schedule.scheduled_talks)
                .select_related('submission_type')
                .prefetch_related('speakers')
            )
        return Submission.objects.none()

    @cached_property
    def speakers(self):
        """Returns a queryset of all speakers (of type.

        :class:`~eventyay.base.models.user.User`) visible in the current
        released schedule.
        """
        from eventyay.base.models import User

        return User.objects.filter(submissions__in=self.talks).order_by('id').distinct()

    @cached_property
    def has_schedule_content(self):
        """Returns True if the current schedule has visible sessions or scheduled breaks.

        This checks whether the current schedule has any visible, scheduled talks
        or breaks (not just an empty published schedule).
        """
        if not self.current_schedule:
            return False
        schedule = self.current_schedule
        if schedule.scheduled_talks.exists():
            return True
        return schedule.breaks.filter(start__isnull=False, is_visible=True).exists()

    @cached_property
    def submitters(self):
        """Returns a queryset of all :class:`~eventyay.base.models.user.User`
        objects who have submitted to this event.

        Ignores users who have deleted all of their submissions.
        """
        from eventyay.base.models import User

        return (
            User.objects.filter(submissions__in=self.submissions.all())
            .prefetch_related('submissions')
            .order_by('id')
            .distinct()
        )

    @cached_property
    def teams(self):
        """Returns all :class:`~eventyay.base.models.organizer.Team` objects
        that concern this event."""

        return self.organizer.teams.filter(
            models.Q(all_events=True) | models.Q(models.Q(all_events=False) & models.Q(limit_events=self))
        ).distinct()

    @cached_property
    def reviewers(self):
        from eventyay.base.models import User

        return User.objects.filter(
            teams__in=self.teams.filter(Q(is_reviewer=True) | Q(can_change_submissions=True))
        ).distinct()

    @cached_property
    def active_review_phase(self):
        if phase := self.review_phases.filter(is_active=True).first():
            return phase
        if not self.review_phases.all().exists():
            from eventyay.base.models import ReviewPhase

            cfp_deadline = self.cfp.deadline
            return ReviewPhase.objects.create(
                event=self,
                name=_('Review'),
                start=cfp_deadline,
                end=self.datetime_from - relativedelta(months=-3),
                is_active=bool(cfp_deadline),
                can_see_other_reviews='after_review',
                can_see_speaker_names=True,
            )

    @cached_property
    def cfp_flow(self):
        from eventyay.cfp.flow import CfPFlow

        return CfPFlow(self)

    def reorder_review_phases(self):
        """Reorder the review phases by start date."""
        # first, sort phases so that the ones with no start date come first
        phases = list(self.review_phases.all())
        placeholder = dt.datetime(1970, 1, 2, tzinfo=dt.UTC)
        phases.sort(key=lambda x: (x.start or placeholder, x.end or placeholder))
        for i, phase in enumerate(phases):
            phase.position = i
            phase.save(update_fields=['position'])

    def update_review_phase(self):
        """This method activates the next review phase if the current one is
        over.

        If no review phase is active and if there is a new one to
        activate.
        """
        _now = now()
        future_phases = self.review_phases.all()
        old_phase = self.active_review_phase
        if old_phase and old_phase.end and old_phase.end > _now:
            return old_phase
        self.reorder_review_phases()
        old_position = old_phase.position if old_phase else -1
        future_phases = future_phases.filter(position__gt=old_position)
        next_phase = future_phases.order_by('position').first()
        if not next_phase or not next_phase.start or next_phase.start > _now:
            return old_phase
        next_phase.activate()
        return next_phase

    update_review_phase.alters_data = True

    def release_schedule(self, name: str, user=None, notify_speakers: bool = False, comment: str = None):
        """Releases a new :class:`~eventyay.base.models.schedule.Schedule`
        by finalising the current WIP schedule.

        :param name: The new version name
        :param user: The :class:`~eventyay.base.models.user.User` executing the release
        :param notify_speakers: Generate emails for all speakers with changed slots.
        :param comment: Public comment for the release
        :type user: :class:`~eventyay.base.models.user.User`
        """
        self.wip_schedule.freeze(name=name, user=user, notify_speakers=notify_speakers, comment=comment)

    release_schedule.alters_data = True

    @cached_property
    def wip_schedule(self):
        """Returns the latest unreleased.

        :class:`~eventyay.base.models.schedule.Schedule`.

        :retval: :class:`~eventyay.base.models.schedule.Schedule`
        """
        try:
            schedule, _ = self.schedules.get_or_create(version__isnull=True)
        except MultipleObjectsReturned:
            # No idea how this happens – a race condition due to transaction weirdness?
            from eventyay.base.models import TalkSlot

            schedules = list(self.schedules.filter(version__isnull=True))
            schedule = schedules[0]
            # It's only ever been two so far, but while we're being resilient …
            for dupe in schedules[1:]:
                TalkSlot.objects.filter(schedule=dupe).delete()
                dupe.delete()
        return schedule

    @cached_property
    def current_schedule(self):
        if pk := getattr(self, '_current_schedule_pk', None):
            # The event middleware prefetches the current schedule
            return self.schedules.get(pk=pk)
        return self.schedules.order_by('-published').filter(published__isnull=False).first()

    def get_mail_template(self, role):
        from eventyay.base.models import MailTemplate
        from eventyay.mail.default_templates import get_default_template
        from i18nfield.strings import LazyI18nString

        try:
            with scope(event=self):
                template = self.mail_templates.get(role=role)
        except MailTemplate.DoesNotExist:
            default_subject, default_text = get_default_template(role)
            # Initialize with all event locales from the start
            subject_data = {}
            text_data = {}
            for locale in self.locales:
                if locale:
                    subject_data[locale] = str(default_subject.localize(locale))
                    text_data[locale] = str(default_text.localize(locale))
            
            subject = LazyI18nString(subject_data) if subject_data else default_subject
            text = LazyI18nString(text_data) if text_data else default_text
            
            with scope(event=self):
                template, __ = MailTemplate.objects.get_or_create(
                    event=self, role=role, defaults={'subject': subject, 'text': text}
                )
        return self._ensure_mail_template_locales(template, role)

    def _ensure_mail_template_locales(self, template, role):
        from eventyay.mail.default_templates import get_default_template

        if role is None:
            return template

        default_subject, default_text = get_default_template(role)
        
        # Pre-check: do we have all locales without needing a write?
        locales_to_check = set(locale for locale in self.locales if locale)
        all_locales_present = True
        
        for field_name, default_value in (('subject', default_subject), ('text', default_text)):
            current_value = getattr(template, field_name)
            if not (
                hasattr(current_value, 'data')
                and isinstance(current_value.data, dict)
                and hasattr(default_value, 'localize')
            ):
                continue
            
            if locales_to_check - set(current_value.data.keys()):
                all_locales_present = False
                break
        
        # Early return if all locales are already present
        if all_locales_present:
            return template
        
        # Only enter transaction if we need to backfill missing locales
        with scope(event=self), transaction.atomic():
            if template.pk:
                template = template.__class__.objects.select_for_update().get(pk=template.pk)

            changed_fields = []
            for field_name, default_value in (('subject', default_subject), ('text', default_text)):
                current_value = getattr(template, field_name)
                if not (
                    hasattr(current_value, 'data')
                    and isinstance(current_value.data, dict)
                    and hasattr(default_value, 'localize')
                ):
                    continue

                field_changed = False
                for locale in self.locales:
                    if locale and locale not in current_value.data:
                        current_value.data[locale] = str(default_value.localize(locale))
                        field_changed = True

                if field_changed:
                    changed_fields.append(field_name)

            if changed_fields:
                template.save(update_fields=changed_fields)
        return template

    def build_initial_data(self):
        from eventyay.base.models import CfP, MailTemplateRoles, Schedule
        from django_scopes import scope

        with scope(event=self):
            if not CfP.objects.filter(event=self).exists():
                CfP.objects.create(event=self, default_type=self._get_default_submission_type())

        with scope(event=self):
            if not self.schedules.filter(version__isnull=True).exists():
                Schedule.objects.create(event=self)

        for role, __ in MailTemplateRoles.choices:
            self.get_mail_template(role)

        with scope(event=self):
            if not self.review_phases.all().exists():
                from eventyay.base.models import ReviewPhase

                cfp_deadline = self.cfp.deadline
                rp = ReviewPhase.objects.create(
                    event=self,
                    name=_('Review'),
                    start=cfp_deadline,
                    end=self.datetime_from - relativedelta(months=-3),
                    is_active=bool(not cfp_deadline or cfp_deadline < now()),
                    position=0,
                )
                ReviewPhase.objects.create(
                    event=self,
                    name=_('Selection'),
                    start=rp.end,
                    is_active=False,
                    position=1,
                    can_review=False,
                    can_see_other_reviews='always',
                    can_change_submission_state=True,
                )

        with scope(event=self):
            if not self.score_categories.all().exists():
                from eventyay.base.models import ReviewScore, ReviewScoreCategory

                category = ReviewScoreCategory.objects.create(
                    event=self,
                    name=str(_('Score')),
                )
                ReviewScore.objects.create(
                    category=category,
                    value=0,
                    label=str(_('No')),
                )
                ReviewScore.objects.create(
                    category=category,
                    value=1,
                    label=str(_('Maybe')),
                )
                ReviewScore.objects.create(
                    category=category,
                    value=2,
                    label=str(_('Yes')),
                )

        self.save()

    build_initial_data.alters_data = True

    @cached_property
    def pending_mails(self) -> int:
        """The amount of currently unsent.

        :class:`~eventyay.base.models.mail.QueuedMail` objects.
        """
        return self.queued_mails.filter(sent__isnull=True, is_draft=False).count()


class EventExtraLink(OrderedModel, PretalxModel):
    event = models.ForeignKey(to='Event', on_delete=models.CASCADE, related_name='extra_links')
    label = I18nCharField(max_length=200, verbose_name=_('Link text'))
    url = models.URLField(verbose_name=_('Link URL'))
    role = models.CharField(
        max_length=6,
        choices=(('footer', 'Footer'), ('header', 'Header')),
        default='footer',
    )

    objects = ScopedManager(event='event')


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
    :type date_from: datetime.datetime
    :param date_to: The datetime this event ends
    :type date_to: datetime.datetime
    :param presale_start: No tickets will be sold before this date.
    :type presale_start: datetime.datetime
    :param presale_end: No tickets will be sold after this date.
    :type presale_end: datetime.datetime
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
    date_to = models.DateTimeField(verbose_name=_('Event end time'))
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

    products = models.ManyToManyField('Product', through='SubEventProduct')
    variations = models.ManyToManyField('ProductVariation', through='SubEventProductVariation')

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
    def product_overrides(self):
        from .product import SubEventProduct

        return {si.product_id: si for si in SubEventProduct.objects.filter(subevent=self)}

    @cached_property
    def var_overrides(self):
        from .product import SubEventProductVariation

        return {si.variation_id: si for si in SubEventProductVariation.objects.filter(subevent=self)}

    @property
    def product_price_overrides(self):
        return {si.product_id: si.price for si in self.product_overrides.values() if si.price is not None}

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
        if self.date_from and not self.date_to:
            self.date_to = self.date_from + timedelta(hours=24)

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
    def clean_products(event, products):
        for product in products:
            if event != product.event:
                raise ValidationError(_('One or more products do not belong to this event.'))

    @staticmethod
    def clean_variations(event, variations):
        for variation in variations:
            if event != variation.product.event:
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

    :param datetime: The timestamp of the required action
    :type datetime: datetime.datetime
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
    event = models.ForeignKey('Event', on_delete=models.CASCADE, related_name='planned_usages')
    start = models.DateField()
    end = models.DateField()
    attendees = models.PositiveIntegerField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ('start',)

    def as_ical(self):
        event = icalendar.Event()
        event['uid'] = f'{self.event.id}-{self.id}'
        event['dtstart'] = self.start
        event['dtend'] = self.start
        event['summary'] = str(self.event.name)
        event['description'] = self.notes
        event['url'] = self.event.domain
        return event


class EventView(models.Model):
    event = models.ForeignKey('Event', related_name='views', on_delete=models.CASCADE)
    start = models.DateTimeField(auto_now_add=True)
    end = models.DateTimeField(null=True, db_index=True)
    user = models.ForeignKey('User', related_name='event_views', on_delete=models.CASCADE)

    class Meta:
        indexes = [models.Index(fields=['start'])]
