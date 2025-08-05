import string
import uuid
import zoneinfo
import copy
import jwt
import json
from collections import OrderedDict, defaultdict
from datetime import datetime, time, timedelta
from operator import attrgetter
from urllib.parse import urljoin, urlparse

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
from eventyay.common.text.path import path_with_hash
from eventyay.common.text.phrases import phrases
from eventyay.common.urls import EventUrls

from ..settings import settings_hierarkey
from .organizer import Organizer, OrganizerBillingModel, Team

from eventyay.core.permissions import Permission, SYSTEM_ROLES
from eventyay.core.utils.json import CustomJSONEncoder

TALK_HOSTNAME = settings.TALK_HOSTNAME
TIMEZONE_CHOICES = sorted([
    tz for tz in zoneinfo.available_timezones() if not tz.startswith("Etc/")
])
LANGUAGE_NAMES = {code: name for code, name in settings.LANGUAGES}

def event_css_path(instance, filename):
    return path_with_hash(filename, base_path=f"{instance.slug}/css/")

def event_logo_path(instance, filename):
    return path_with_hash(filename, base_path=f"{instance.slug}/img/")

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
    room_owner = participant + [Permission.ROOM_INVITE, Permission.ROOM_DELETE]
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
    return {"attendee": ["attendee"], "admin": ["admin"], "scheduleuser": ["schedule-update"]}

def default_feature_flags():
    return {
        "show_schedule": True,
        "show_featured": "pre_schedule",
        "show_widget_if_not_public": False,
        "export_html_on_release": False,
        "use_tracks": True,
        "use_feedback": True,
        "use_submission_comments": True,
        "present_multiple_times": False,
        "submission_public_review": True,
        "chat-moderation": True,
        "schedule-control": False,
        "iframe-player": False,
        "roulette": False,
        "muxdata": False,
        "page.landing": False,
        "zoom": False,
        "janus": False,
        "polls": False,
        "poster": False,
        "conftool": False,
        "cross-origin-isolation": False,
    }

def default_display_settings():
    return {
        "schedule": "grid",
        "imprint_url": None,
        "header_pattern": "",
        "html_export_url": "",
        "meta_noindex": False,
        "texts": {"agenda_session_above": "", "agenda_session_below": ""},
    }

def default_review_settings():
    return {
        "score_mandatory": False,
        "text_mandatory": False,
        "aggregate_method": "median",
        "score_format": "words_numbers",
    }

def default_mail_settings():
    return {
        "mail_from": "",
        "reply_to": "",
        "signature": "",
        "subject_prefix": "",
        "smtp_use_custom": "",
        "smtp_host": "",
        "smtp_port": 587,
        "smtp_username": "",
        "smtp_password": "",
        "smtp_use_tls": "",
        "smtp_use_ssl": "",
        "mail_on_new_submission": False,
    }

class EventMixin:
    def clean(self):
        if self.presale_start and self.presale_end and self.presale_start > self.presale_end:
            raise ValidationError({'presale_end': _('The end of the presale period has to be later than its start.')})
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValidationError({'date_to': _('The end of the event has to be later than its start.')})
        super().clean()

    def get_short_date_from_display(self, tz=None, show_times=True) -> str:
        tz = tz or self.timezone
        return _date(
            self.date_from.astimezone(tz),
            ('SHORT_DATETIME_FORMAT' if self.settings.show_times and show_times else 'DATE_FORMAT'),
        )
    def get_short_date_to_display(self, tz=None) -> str:
        tz = tz or self.timezone
        if not self.settings.show_date_to or not self.date_to:
            return ''
        return _date(
            self.date_to.astimezone(tz),
            'SHORT_DATETIME_FORMAT' if self.settings.show_times else 'DATE_FORMAT',
        )
    def get_date_from_display(self, tz=None, show_times=True, short=False) -> str:
        tz = tz or self.timezone
        return _date(
            self.date_from.astimezone(tz),
            ('SHORT_' if short else '')
            + ('DATETIME_FORMAT' if self.settings.show_times and show_times else 'DATE_FORMAT'),
        )
    def get_time_from_display(self, tz=None) -> str:
        tz = tz or self.timezone
        return _date(self.date_from.astimezone(tz), 'TIME_FORMAT')
    def get_date_to_display(self, tz=None, show_times=True, short=False) -> str:
        tz = tz or self.timezone
        if not self.settings.show_date_to or not self.date_to:
            return ''
        return _date(
            self.date_to.astimezone(tz),
            ('SHORT_' if short else '')
            + ('DATETIME_FORMAT' if self.settings.show_times and show_times else 'DATE_FORMAT'),
        )
    def get_date_range_display(self, tz=None, force_show_end=False) -> str:
        tz = tz or self.timezone
        if (not self.settings.show_date_to and not force_show_end) or not self.date_to:
            return _date(self.date_from.astimezone(tz), 'DATE_FORMAT')
        return daterange(self.date_from.astimezone(tz), self.date_to.astimezone(tz))
    @property
    def timezone(self):
        return pytz.timezone(self.settings.timezone)
    @property
    def effective_presale_end(self):
        if isinstance(self, SubEvent):
            presale_ends = [self.presale_end, self.event.presale_end]
            return min(filter(lambda x: x is not None, presale_ends)) if any(presale_ends) else None
        else:
            return self.presale_end
    @property
    def presale_has_ended(self):
        if self.effective_presale_end:
            return now() > self.effective_presale_end
        elif self.date_to:
            return now() > self.date_to
        else:
            return now().astimezone(self.timezone).date() > self.date_from.astimezone(self.timezone).date()
    @property
    def effective_presale_start(self):
        if isinstance(self, SubEvent):
            presale_starts = [self.presale_start, self.event.presale_start]
            return max(filter(lambda x: x is not None, presale_starts)) if any(presale_starts) else None
        else:
            return self.presale_start
    @property
    def presale_is_running(self):
        if self.effective_presale_start and now() < self.effective_presale_start:
            return False
        return not self.presale_has_ended
    @property
    def event_microdata(self):
        eventdict = {
            "@context": "http://schema.org",
            "@type": "Event",
            "location": {"@type": "Place", "address": str(self.location)},
            "name": str(self.name),
        }
        img = getattr(self, "event", self).social_image
        if img:
            eventdict["image"] = img
        if self.settings.show_times:
            eventdict["startDate"] = self.date_from.isoformat()
            if self.settings.show_date_to and self.date_to is not None:
                eventdict["endDate"] = self.date_to.isoformat()
        else:
            eventdict["startDate"] = self.date_from.date().isoformat()
            if self.settings.show_date_to and self.date_to is not None:
                eventdict["endDate"] = self.date_to.date().isoformat()
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
        items_available, vars_available = set(), set()
        items_reserved, vars_reserved = set(), set()
        items_gone, vars_gone = set(), set()
        r = getattr(self, '_quota_cache', {})
        for q in self.active_quotas:
            res = r.get(q, q.availability(allow_cache=True))
            if res[0] == Quota.AVAILABILITY_OK:
                if q.active_items: items_available.update(q.active_items.split(','))
                if q.active_variations: vars_available.update(q.active_variations.split(','))
            elif res[0] == Quota.AVAILABILITY_RESERVED:
                if q.active_items: items_reserved.update(q.active_items.split(','))
                if q.active_variations: vars_reserved.update(q.active_variations.split(','))
            elif res[0] < Quota.AVAILABILITY_RESERVED:
                if q.active_items: items_gone.update(q.active_items.split(','))
                if q.active_variations: vars_gone.update(q.active_variations.split(','))
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
    settings_namespace = 'event'
    _event_id = 'pk'
    CURRENCY_CHOICES = [(c.alpha_3, f'{c.alpha_3} - {c.name}') for c in settings.CURRENCIES]

    organizer = models.ForeignKey(Organizer, related_name='events', on_delete=models.PROTECT)
    testmode = models.BooleanField(default=False)
    name = I18nCharField(max_length=200, verbose_name=_('Event name'))
    slug = models.CharField(
        max_length=50, db_index=True, verbose_name=_('Short form'),
        help_text=_(
            'Should be short, only contain lowercase letters, numbers, dots, and dashes, and must be unique among your '
            'events. This will be used in URLs, order codes, invoice numbers, and bank transfer references.'
        ),
        validators=[
            MinLengthValidator(limit_value=2),
            RegexValidator(regex='^[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9]$', message=_('The slug may only contain letters, numbers, dots and dashes.')),
            EventSlugBanlistValidator(),
        ],
    )
    live = models.BooleanField(default=False, verbose_name=_('Shop is live'))
    currency = models.CharField(max_length=10, verbose_name=_('Event currency'), choices=CURRENCY_CHOICES, default=settings.DEFAULT_CURRENCY)
    date_from = models.DateTimeField(verbose_name=_('Event start time'))
    date_to = models.DateTimeField(null=True, blank=True, verbose_name=_('Event end time'))
    date_admission = models.DateTimeField(null=True, blank=True, verbose_name=_('Admission time'))
    is_public = models.BooleanField(default=True, verbose_name=_('Show in lists'), help_text=_('If selected, this event will show up publicly on the list of events for your organizer account.'))
    presale_end = models.DateTimeField(null=True, blank=True, verbose_name=_('End of presale'), help_text=_('Optional. No products will be sold after this date.'))
    presale_start = models.DateTimeField(null=True, blank=True, verbose_name=_('Start of presale'), help_text=_('Optional. No products will be sold before this date.'))
    location = I18nTextField(null=True, blank=True, max_length=200, verbose_name=_('Location'))
    geo_lat = models.FloatField(verbose_name=_('Latitude'), null=True, blank=True, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    geo_lon = models.FloatField(verbose_name=_('Longitude'), null=True, blank=True, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    plugins = models.TextField(null=False, blank=True, verbose_name=_('Plugins'))
    comment = models.TextField(verbose_name=_('Internal comment'), null=True, blank=True)
    has_subevents = models.BooleanField(verbose_name=_('Event series'), default=False)
    seating_plan = models.ForeignKey('SeatingPlan', on_delete=models.PROTECT, null=True, blank=True, related_name='events')
    sales_channels = MultiStringField(verbose_name=_('Restrict to specific sales channels'), help_text=_('Only sell tickets for this event on the following sales channels.'), default=['web'])
    is_video_creation = models.BooleanField(verbose_name=_('Add video call'), help_text=_('Create Video platform for Event.'), default=False)

    # Talk / Pretalx fields
    timezone = models.CharField(choices=[(tz, tz) for tz in TIMEZONE_CHOICES], max_length=120, default="Europe/Berlin")
    email = models.EmailField(verbose_name=_("Organiser email address"), help_text=_("Will be used as Reply-To in emails."), default="org@mail.com")
    custom_domain = models.URLField(verbose_name=_("Custom domain"), help_text=_("Enter a custom domain, e.g. https://my.event.example.org"), null=True, blank=True)
    display_settings = models.JSONField(default=default_display_settings)
    review_settings = models.JSONField(default=default_review_settings)
    mail_settings = models.JSONField(default=default_mail_settings)
    primary_color = models.CharField(max_length=7, null=True, blank=True, validators=[RegexValidator("#([0-9A-Fa-f]{3}){1,2}")], verbose_name=_("Main event colour"))
    custom_css = models.FileField(upload_to=event_css_path, null=True, blank=True, verbose_name=_("Custom Event CSS"))
    logo = models.ImageField(upload_to=event_logo_path, null=True, blank=True, verbose_name=_("Logo"))
    header_image = models.ImageField(upload_to=event_logo_path, null=True, blank=True, verbose_name=_("Header image"))
    locale_array = models.TextField(default=settings.LANGUAGE_CODE)
    content_locale_array = models.TextField(default=settings.LANGUAGE_CODE)
    locale = models.CharField(max_length=32, default=settings.LANGUAGE_CODE, choices=settings.LANGUAGES, verbose_name=_("Default language"))
    landing_page_text = I18nTextField(verbose_name=_("Landing page text"), null=True, blank=True)
    featured_sessions_text = I18nTextField(verbose_name=_("Featured sessions text"), null=True, blank=True)

    # Virtual platform fields
    config = models.JSONField(null=True, blank=True)
    roles = models.JSONField(null=True, blank=True, default=default_roles, encoder=CustomJSONEncoder)
    trait_grants = models.JSONField(null=True, blank=True, default=default_grants)
    domain = models.CharField(max_length=250, unique=True, null=True, blank=True, validators=[RegexValidator(regex=r"^[a-z0-9-.:]+(/[a-zA-Z0-9-_./]*)?$")])
    feature_flags = models.JSONField(default=default_feature_flags)
    external_auth_url = models.URLField(null=True, blank=True)

    objects = ScopedManager(organizer='organizer')

    HEADER_PATTERN_CHOICES = (
        ("", _("Plain")), ("pcb", _("Circuits")), ("bubbles", _("Circles")),
        ("signal", _("Signal")), ("topo", _("Topography")), ("graph", _("Graph Paper")),
    )


    class urls(EventUrls):
        base_path = settings.BASE_PATH
        base = "{base_path}/{self.slug}/"
        login = "{base}login/"
        logout = "{base}logout"
        auth = "{base}auth/"
        logo = "{self.logo.url}"
        social_image = "{base}og-image"
        reset = "{base}reset"
        submit = "{base}submit/"
        user = "{base}me/"
        user_delete = "{base}me/delete"
        user_submissions = "{user}submissions/"
        user_mails = "{user}mails/"
        schedule = "{base}schedule/"
        schedule_nojs = "{schedule}nojs"
        featured = "{base}featured/"
        talks = "{base}talk/"
        speakers = "{base}speaker/"
        changelog = "{schedule}changelog/"
        feed = "{schedule}feed.xml"
        export = "{schedule}export/"
        frab_xml = "{export}schedule.xml"
        frab_json = "{export}schedule.json"
        frab_xcal = "{export}schedule.xcal"
        ical = "{export}schedule.ics"
        schedule_widget_data = "{schedule}widgets/schedule.json"
        schedule_widget_script = "{base}widgets/schedule.js"
        settings_css = "{base}static/event.css"

    class orga_urls(EventUrls):
        base_path = settings.BASE_PATH
        base = "{base_path}/orga/event/{self.slug}/"
        login = "{base}login/"
        live = "{base}live"
        delete = "{base}delete"
        cfp = "{base}cfp/"
        history = "{base}history/"
        users = "{base}api/users"
        mail = "{base}mails/"
        compose_mails = "{mail}compose"
        compose_mails_sessions = "{compose_mails}/sessions/"
        compose_mails_teams = "{compose_mails}/teams/"
        send_drafts_reminder = "{compose_mails}/reminders"
        mail_templates = "{mail}templates/"
        new_template = "{mail_templates}new/"
        outbox = "{mail}outbox/"
        sent_mails = "{mail}sent"
        send_outbox = "{outbox}send"
        purge_outbox = "{outbox}purge"
        submissions = "{base}submissions/"
        tags = "{submissions}tags/"
        new_tag = "{tags}new/"
        submission_cards = "{base}submissions/cards/"
        stats = "{base}submissions/statistics/"
        submission_feed = "{base}submissions/feed/"
        new_submission = "{submissions}new"
        feedback = "{submissions}feedback/"
        apply_pending = "{submissions}apply-pending/"
        speakers = "{base}speakers/"
        settings = edit_settings = "{base}settings/"
        review_settings = "{settings}review/"
        mail_settings = edit_mail_settings = "{settings}mail"
        widget_settings = "{settings}widget"
        team_settings = "{settings}team/"
        new_team = "{settings}team/new"
        room_settings = "{schedule}rooms/"
        new_room = "{room_settings}new/"
        schedule = "{base}schedule/"
        schedule_export = "{schedule}export/"
        schedule_export_trigger = "{schedule_export}trigger"
        schedule_export_download = "{schedule_export}download"
        release_schedule = "{schedule}release"
        reset_schedule = "{schedule}reset"
        toggle_schedule = "{schedule}toggle"
        reviews = "{base}reviews/"
        review_assignments = "{reviews}assign/"
        schedule_api = "{base}schedule/api/"
        talks_api = "{schedule_api}talks/"
        plugins = "{settings}plugins"
        information = "{base}info/"
        new_information = "{base}info/new/"

    class api_urls(EventUrls):
        base_path = settings.TALK_BASE_PATH
        base = "{base_path}/api/events/{self.slug}/"
        submissions = "{base}submissions/"
        slots = "{base}slots/"
        talks = "{base}talks/"
        schedules = "{base}schedules/"
        speakers = "{base}speakers/"
        reviews = "{base}reviews/"
        rooms = "{base}rooms/"
        questions = "{base}questions/"
        question_options = "{base}question-options/"
        answers = "{base}answers/"
        tags = "{base}tags/"
        tracks = "{base}tracks/"
        submission_types = "{base}submission-types/"
        mail_templates = "{base}mail-templates/"
        access_codes = "{base}access-codes/"
        speaker_information = "{base}speaker-information/"

    class tickets_urls(EventUrls):
        _full_base_path = settings.BASE_PATH
        base_path = urlparse(_full_base_path).path.rstrip('/')
        base = "{base_path}/control/"
        common = "{base_path}/common/"
        tickets_home_common = "{common}event/{self.organiser.slug}/{self.slug}/"
        tickets_dashboard_url = "{base}event/{self.organiser.slug}/{self.slug}/"

    class Meta:
        verbose_name = _('Event')
        verbose_name_plural = _('Events')
        ordering = ('date_from', 'name')
        unique_together = (('organizer', 'slug'),)

    def __str__(self):
        return str(self.name)


    def set_defaults(self):
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
        super().save(*args, **kwargs)
        if hasattr(self, 'cache'):
            self.cache.clear()

    def get_plugins(self):
        return self.plugins.split(',') if self.plugins else []

    @cached_property
    def cache(self):
        from eventyay.base.cache import ObjectRelatedCache
        return ObjectRelatedCache(self)

    def lock(self):
        from eventyay.base.services import locking
        return locking.LockManager(self)

    def get_mail_backend(self, timeout=None, force_custom=False):
        from eventyay.base.email import CustomSMTPBackend, SendGridEmail
        gs = GlobalSettingsObject()
        if self.settings.smtp_use_custom or force_custom:
            if self.settings.email_vendor == 'sendgrid':
                return SendGridEmail(api_key=self.settings.send_grid_api_key)
            return CustomSMTPBackend(
                host=self.settings.smtp_host, port=self.settings.smtp_port,
                username=self.settings.smtp_username, password=self.settings.smtp_password,
                use_tls=self.settings.smtp_use_tls, use_ssl=self.settings.smtp_use_ssl,
                fail_silently=False, timeout=timeout,
            )
        elif gs.settings.email_vendor is not None:
            if gs.settings.email_vendor == 'sendgrid':
                return SendGridEmail(api_key=gs.settings.send_grid_api_key)
            else:
                return CustomSMTPBackend(
                    host=gs.settings.smtp_host, port=gs.settings.smtp_port,
                    username=gs.settings.smtp_username, password=gs.settings.smtp_password,
                    use_tls=gs.settings.smtp_use_tls, use_ssl=gs.settings.smtp_use_ssl,
                    fail_silently=False, timeout=timeout,
                )
        else:
            return get_connection(fail_silently=False)

    @property
    def payment_term_last(self):
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


    def decode_token(self, token, allow_raise=False):
        exc = None
        for jwt_config in self.config.get("JWT_secrets", []):
            secret = jwt_config["secret"]
            audience = jwt_config["audience"]
            issuer = jwt_config["issuer"]
            try:
                return jwt.decode(token, secret, algorithms=["HS256"], audience=audience, issuer=issuer)
            except jwt.exceptions.ExpiredSignatureError:
                if allow_raise:
                    raise
            except jwt.exceptions.InvalidTokenError as e:
                exc = e
        if exc and allow_raise:
            raise exc

    def has_permission_implicit(self, *, traits, permissions, room=None, allow_empty_traits=True):
        for role, required_traits in self.trait_grants.items():
            if (
                isinstance(required_traits, list)
                and all(any(x in traits for x in (r if isinstance(r, list) else [r])) for r in required_traits)
                and (required_traits or allow_empty_traits)
            ):
                if any(p.value in self.roles.get(role, SYSTEM_ROLES.get(role, [])) for p in permissions):
                    return True
            if room:
                for role, required_traits in getattr(room, 'trait_grants', {}).items():
                    if (
                        isinstance(required_traits, list)
                        and all(any(x in traits for x in (r if isinstance(r, list) else [r])) for r in required_traits)
                        and (required_traits or allow_empty_traits)
                    ):
                        if any(p.value in self.roles.get(role, SYSTEM_ROLES.get(role, [])) for p in permissions):
                            return True
        return False

    def has_permission(self, *, user, permission, room=None):
        from .auth import User
        if getattr(user, 'is_banned', False):
            return False
        if not isinstance(permission, list):
            permission = [permission]
        if getattr(user, 'is_silenced', False) and not any(p in MAX_PERMISSIONS_IF_SILENCED for p in permission):
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
            if any(p.value in self.roles.get(r, SYSTEM_ROLES.get(r, [])) for p in permission):
                return True
        return False

    async def has_permission_async(self, *, user, permission, room=None):
        from .auth import User
        if getattr(user, 'is_banned', False):
            return False
        if not isinstance(permission, list):
            permission = [permission]
        if getattr(user, 'is_silenced', False) and not any(p in MAX_PERMISSIONS_IF_SILENCED for p in permission):
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
            if any(p.value in self.roles.get(r, SYSTEM_ROLES.get(r, [])) for p in permission):
                return True
        return False

    def get_all_permissions(self, user):
        from .auth import User
        result = defaultdict(set)
        if getattr(user, 'is_banned', False):
            return result
        allow_empty_traits = getattr(user, 'type', None) == getattr(User, 'UserType', None) and user.type == User.UserType.PERSON
        for role, required_traits in self.trait_grants.items():
            if (
                isinstance(required_traits, list)
                and all(any(x in getattr(user, 'traits', [])) for x in (r if isinstance(r, list) else [r]) for r in required_traits)
                and (required_traits or allow_empty_traits)
            ):
                result[self].update(self.roles.get(role, SYSTEM_ROLES.get(role, [])))
        for grant in getattr(user, 'event_grants', []).all():
            result[self].update(self.roles.get(grant.role, SYSTEM_ROLES.get(grant.role, [])))
        for room in getattr(self, 'rooms', []).all():
            for role, required_traits in getattr(room, 'trait_grants', {}).items():
                if (
                    isinstance(required_traits, list)
                    and all(any(x in getattr(user, 'traits', []) for x in (r if isinstance(r, list) else [r])) for r in required_traits)
                    and (required_traits or allow_empty_traits)
                ):
                    result[room].update(self.roles.get(role, SYSTEM_ROLES.get(role, [])))
        for grant in getattr(user, 'room_grants', []).select_related("room"):
            result[grant.room].update(self.roles.get(grant.role, SYSTEM_ROLES.get(grant.role, [])))
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

    @cached_property
    def locales(self) -> list[str]:
        return self.locale_array.split(",")

    @cached_property
    def content_locales(self) -> list[str]:
        return self.content_locale_array.split(",")

    @cached_property
    def is_multilingual(self) -> bool:
        return len(self.content_locales) > 1

    @cached_property
    def named_locales(self) -> list:
        return [
            (lang["code"], lang["natural_name"])
            for lang in settings.LANGUAGES_INFORMATION.values()
            if lang["code"] in self.locales
        ]

    @cached_property
    def available_content_locales(self) -> list:
        locale_names = copy.copy(LANGUAGE_NAMES)
        locale_names.update(getattr(self, 'named_plugin_locales', {}))
        return sorted([(k, v) for k, v in locale_names.items()])

    @cached_property
    def named_content_locales(self) -> list:
        locale_names = dict(self.available_content_locales)
        return [(code, locale_names[code]) for code in self.content_locales]

class SubEvent(EventMixin, LoggedModel):
    _event_id = 'event_id'
    event = models.ForeignKey(Event, related_name='subevents', on_delete=models.PROTECT)
    active = models.BooleanField(default=False, verbose_name=_('Active'), help_text=_('Only with this checkbox enabled, this date is visible in the frontend to users.'))
    is_public = models.BooleanField(default=True, verbose_name=_('Show in lists'), help_text=_('If selected, this event will show up publicly on the list of dates for your event.'))
    name = I18nCharField(max_length=200, verbose_name=_('Name'))
    date_from = models.DateTimeField(verbose_name=_('Event start time'))
    date_to = models.DateTimeField(null=True, blank=True, verbose_name=_('Event end time'))
    date_admission = models.DateTimeField(null=True, blank=True, verbose_name=_('Admission time'))
    presale_end = models.DateTimeField(null=True, blank=True, verbose_name=_('End of presale'))
    presale_start = models.DateTimeField(null=True, blank=True, verbose_name=_('Start of presale'))
    location = I18nTextField(null=True, blank=True, max_length=200, verbose_name=_('Location'))
    geo_lat = models.FloatField(verbose_name=_('Latitude'), null=True, blank=True, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    geo_lon = models.FloatField(verbose_name=_('Longitude'), null=True, blank=True, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    frontpage_text = I18nTextField(null=True, blank=True, verbose_name=_('Frontpage text'))
    seating_plan = models.ForeignKey('SeatingPlan', on_delete=models.PROTECT, null=True, blank=True, related_name='subevents')
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
    organizer = models.ForeignKey(Organizer, related_name='meta_properties', on_delete=models.CASCADE)
    name = models.CharField(
        max_length=50,
        db_index=True,
        help_text=_('Can not contain spaces or special characters except underscores'),
        validators=[RegexValidator(regex='^[a-zA-Z0-9_]+$', message=_('The property name may only contain letters, numbers and underscores.'))],
        verbose_name=_('Name'),
    )
    default = models.TextField(blank=True, verbose_name=_('Default value'))
    protected = models.BooleanField(default=False, verbose_name=_('Can only be changed by organizer-level administrators'))
    required = models.BooleanField(
        default=False,
        verbose_name=_('Required for events'),
        help_text=_('If checked, an event can only be taken live if the property is set. In event series, its always optional to set a value for individual dates'),
    )
    allowed_values = models.TextField(null=True, blank=True, verbose_name=_('Valid values'))

    def full_clean(self, exclude=None, validate_unique=True):
        super().full_clean(exclude, validate_unique)
        if self.default and self.required:
            raise ValidationError(_('A property can either be required or have a default value, not both.'))
        if self.default and self.allowed_values and self.default not in self.allowed_values.splitlines():
            raise ValidationError(_('You cannot set a default value that is not a valid value.'))

class EventMetaValue(LoggedModel):
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
    event = models.ForeignKey('Event', on_delete=models.CASCADE, related_name="planned_usages")
    start = models.DateField()
    end = models.DateField()
    attendees = models.PositiveIntegerField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("start",)

    def as_ical(self):
        import icalendar
        event = icalendar.Event()
        event["uid"] = f"{self.event.id}-{self.id}"
        event["dtstart"] = self.start
        event["dtend"] = self.start
        event["summary"] = str(self.event.name)
        event["description"] = self.notes
        event["url"] = self.event.domain
        return event

class EventView(models.Model):
    event = models.ForeignKey('Event', related_name="views", on_delete=models.CASCADE)
    start = models.DateTimeField(auto_now_add=True)
    end = models.DateTimeField(null=True, db_index=True)
    user = models.ForeignKey('User', related_name="event_views", on_delete=models.CASCADE)

    class Meta:
        indexes = [models.Index(fields=["start"])]