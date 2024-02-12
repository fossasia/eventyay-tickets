import copy
import datetime as dt
import zoneinfo

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned, ValidationError
from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.utils.functional import cached_property
from django.utils.timezone import make_aware, now
from django.utils.translation import gettext_lazy as _
from django_scopes import scopes_disabled
from i18nfield.fields import I18nCharField, I18nTextField

from pretalx.common.cache import ObjectRelatedCache
from pretalx.common.language import LANGUAGE_NAMES
from pretalx.common.mixins.models import PretalxModel
from pretalx.common.models import TIMEZONE_CHOICES
from pretalx.common.models.settings import hierarkey
from pretalx.common.phrases import phrases
from pretalx.common.plugins import get_all_plugins
from pretalx.common.urls import EventUrls
from pretalx.common.utils import daterange, path_with_hash

# Slugs need to start and end with an alphanumeric character,
# but may contain dashes and dots in between.
SLUG_CHARS = "a-zA-Z0-9.-"
SLUG_REGEX = rf"[a-zA-Z0-9]([{SLUG_CHARS}]*[a-zA-Z0-9])?"
FULL_SLUG_REGEX = rf"^{SLUG_REGEX}$"


def validate_event_slug_permitted(value):
    forbidden = [
        "_global",
        "__debug__",
        "api",
        "csp_report",
        "events",
        "download",
        "healthcheck",
        "jsi18n",
        "locale",
        "metrics",
        "orga",
        "redirect",
        "relay",
        "widget",
        "400",
        "403",
        "404",
        "500",
        "p",
    ]
    if value.lower() in forbidden:
        raise ValidationError(
            _("Invalid event slug – this slug is reserved: {value}.").format(
                value=value
            ),
            code="invalid",
            params={"value": value},
        )


def event_css_path(instance, filename):
    return f"{instance.slug}/css/{path_with_hash(filename)}"


def event_logo_path(instance, filename):
    return f"{instance.slug}/img/{path_with_hash(filename)}"


def default_feature_flags():
    return {
        "show_schedule": True,
        "show_featured": "pre_schedule",  # or always, or never
        "show_widget_if_not_public": False,
        "export_html_on_release": False,
        "use_tracks": True,
        "use_feedback": True,
        "present_multiple_times": False,
    }


def default_display_settings():
    return {
        "schedule": "grid",  # or list
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
        "aggregate_method": "median",  # or mean
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


@hierarkey.add()
class Event(PretalxModel):
    """The Event class has direct or indirect relations to all other models.

    Since most models depend on the Event model in some way, they should
    preferably be accessed via the reverse relation on the event model to
    prevent data leaks.

    :param is_public: Is this event public yet? Should only be set via the
        ``pretalx.orga.views.EventLive`` view after the warnings have been
        acknowledged.
    :param locale_array: Contains the event's active locales as a comma
        separated string. Please use the ``locales`` property to interact
        with this information.
    :param accept_template: Templates for emails sent when accepting a talk.
    :param reject_template: Templates for emails sent when rejecting a talk.
    :param ack_template: Templates for emails sent when acknowledging that
        a submission was sent in.
    :param update_template: Templates for emails sent when a talk scheduling
        was modified.
    :param question_template: Templates for emails sent when a speaker has not
        yet answered a question, and organisers send out reminders.
    :param primary_color: Main event colour. Accepts hex values like
        ``#00ff00``.
    :param custom_css: Custom event CSS. Has to pass fairly restrictive
        validation for security considerations.
    :param custom_domain: Custom event domain.
    :param logo: Replaces the event name in the public header. Will be
        displayed at up to full header height and up to full content width.
    :param header_image: Replaces the header pattern and/or background
        colour. Centred, so when the window shrinks, the centre will
        continue to be displayed.
    :param plugins: A list of active plugins as a comma-separated string.
        Please use the ``plugin_list`` property for interaction.
    """

    name = I18nCharField(max_length=200, verbose_name=_("Name"))
    slug = models.SlugField(
        max_length=50,
        db_index=True,
        unique=True,
        validators=[
            RegexValidator(
                regex=FULL_SLUG_REGEX,
                message=_(
                    "The slug may only contain letters, numbers, dots and dashes."
                ),
            ),
            validate_event_slug_permitted,
        ],
        verbose_name=_("Short form"),
        help_text=_("The slug may only contain letters, numbers, dots and dashes."),
    )
    organiser = models.ForeignKey(
        to="Organiser",
        null=True,  # backwards compatibility, won't ever be empty
        related_name="events",
        on_delete=models.PROTECT,
    )
    is_public = models.BooleanField(default=False, verbose_name=_("Event is public"))
    date_from = models.DateField(verbose_name=_("Event start date"))
    date_to = models.DateField(verbose_name=_("Event end date"))
    timezone = models.CharField(
        choices=[(tz, tz) for tz in TIMEZONE_CHOICES],
        max_length=32,
        default="UTC",
        help_text=_(
            "All event dates will be localised and interpreted to be in this timezone."
        ),
    )
    email = models.EmailField(
        verbose_name=_("Organiser email address"),
        help_text=_("Will be used as Reply-To in emails."),
    )
    custom_domain = models.URLField(
        verbose_name=_("Custom domain"),
        help_text=_("Enter a custom domain, such as https://my.event.example.org"),
        null=True,
        blank=True,
    )
    feature_flags = models.JSONField(default=default_feature_flags)
    display_settings = models.JSONField(default=default_display_settings)
    review_settings = models.JSONField(default=default_review_settings)
    mail_settings = models.JSONField(default=default_mail_settings)
    primary_color = models.CharField(
        max_length=7,
        null=True,
        blank=True,
        validators=[
            RegexValidator(r"#([0-9A-Fa-f]{3}){1,2}"),
        ],
        verbose_name=_("Main event colour"),
        help_text=_(
            "Provide a hex value like #00ff00 if you want to style pretalx in your event's colour scheme."
        ),
    )
    custom_css = models.FileField(
        upload_to=event_css_path,
        null=True,
        blank=True,
        verbose_name=_("Custom Event CSS"),
        help_text=_(
            "Upload a custom CSS file if changing the primary colour is not sufficient for you."
        ),
    )
    logo = models.FileField(
        upload_to=event_logo_path,
        null=True,
        blank=True,
        verbose_name=_("Logo"),
        help_text=_(
            "If you provide a logo image, your event's name will not be shown in the event header. "
            "The logo will be scaled down to a height of 150px."
        ),
    )
    header_image = models.FileField(
        upload_to=event_logo_path,
        null=True,
        blank=True,
        verbose_name=_("Header image"),
        help_text=_(
            "If you provide a header image, it will be displayed instead of your event's color and/or header pattern "
            "at the top of all event pages. It will be center-aligned, so when the window shrinks, the center parts will "
            "continue to be displayed, and not stretched."
        ),
    )
    locale_array = models.TextField(default=settings.LANGUAGE_CODE)
    content_locale_array = models.TextField(default=settings.LANGUAGE_CODE)
    locale = models.CharField(
        max_length=32,
        default=settings.LANGUAGE_CODE,
        choices=settings.LANGUAGES,
        verbose_name=_("Default language"),
    )
    accept_template = models.ForeignKey(
        to="mail.MailTemplate",
        on_delete=models.CASCADE,
        related_name="+",
        null=True,
        blank=True,
    )
    ack_template = models.ForeignKey(
        to="mail.MailTemplate",
        on_delete=models.CASCADE,
        related_name="+",
        null=True,
        blank=True,
    )
    reject_template = models.ForeignKey(
        to="mail.MailTemplate",
        on_delete=models.CASCADE,
        related_name="+",
        null=True,
        blank=True,
    )
    update_template = models.ForeignKey(
        to="mail.MailTemplate",
        on_delete=models.CASCADE,
        related_name="+",
        null=True,
        blank=True,
    )
    question_template = models.ForeignKey(
        to="mail.MailTemplate",
        on_delete=models.CASCADE,
        related_name="+",
        null=True,
        blank=True,
    )
    landing_page_text = I18nTextField(
        verbose_name=_("Landing page text"),
        help_text=_(
            "This text will be shown on the landing page, alongside with links to the CfP and schedule, if appropriate."
        )
        + " "
        + phrases.base.use_markdown,
        null=True,
        blank=True,
    )
    featured_sessions_text = I18nTextField(
        verbose_name=_("Featured sessions text"),
        help_text=_(
            "This text will be shown at the top of the featured sessions page instead of the default text."
        )
        + " "
        + phrases.base.use_markdown,
        null=True,
        blank=True,
    )
    plugins = models.TextField(null=True, blank=True, verbose_name=_("Plugins"))

    template_names = [
        f"{t}_template" for t in ("accept", "ack", "reject", "update", "question")
    ]

    objects = models.Manager()

    class urls(EventUrls):
        base = "/{self.slug}/"
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

    class orga_urls(EventUrls):
        create = "/orga/event/new"
        base = "/orga/event/{self.slug}/"
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
        new_template = "{mail_templates}new"
        outbox = "{mail}outbox/"
        sent_mails = "{mail}sent"
        send_outbox = "{outbox}send"
        purge_outbox = "{outbox}purge"
        submissions = "{base}submissions/"
        tags = "{submissions}tags/"
        new_tag = "{tags}new"
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
        new_room = "{room_settings}new"
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
        new_information = "{base}info/new"

    class api_urls(EventUrls):
        base = "/api/events/{self.slug}/"
        submissions = "{base}submissions/"
        talks = "{base}talks/"
        schedules = "{base}schedules/"
        speakers = "{base}speakers/"
        reviews = "{base}reviews/"
        rooms = "{base}rooms/"
        questions = "{base}questions/"
        answers = "{base}answers/"
        tags = "{base}tags/"

    class Meta:
        ordering = ("date_from",)

    def __str__(self) -> str:
        return str(self.name)

    @cached_property
    def locales(self) -> list:
        """Is a list of active event locales."""
        return self.locale_array.split(",")

    @cached_property
    def content_locales(self) -> list:
        """Is a list of active content locales."""
        return self.content_locale_array.split(",")

    @cached_property
    def is_multilingual(self) -> bool:
        """Is ``True`` if the event supports more than one locale."""
        return len(self.content_locales) > 1

    @cached_property
    def named_locales(self) -> list:
        """Is a list of tuples of locale codes and natural names for this
        event."""
        return [
            (language["code"], language["natural_name"])
            for language in settings.LANGUAGES_INFORMATION.values()
            if language["code"] in self.locales
        ]

    @cached_property
    def available_content_locales(self) -> list:
        # Content locales can be anything pretalx knows as a language, merged with
        # this event's plugin locales.

        locale_names = copy.copy(LANGUAGE_NAMES)
        locale_names.update(self.named_plugin_locales)
        return sorted([(key, value) for key, value in locale_names.items()])

    @cached_property
    def named_content_locales(self) -> list:
        locale_names = dict(self.available_content_locales)
        return [(a, locale_names[a]) for a in self.content_locales]

    @cached_property
    def named_plugin_locales(self) -> list:
        from pretalx.common.signals import register_locales

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
        return sorted(list(self.named_plugin_locales.keys()))

    @cached_property
    def cache(self):
        """Returns an :py:class:`ObjectRelatedCache` object.

        This behaves equivalent to Django's built-in cache backends, but
        puts you into an isolated environment for this event, so you
        don't have to prefix your cache keys.
        """
        return ObjectRelatedCache(self, field="slug")

    def save(self, *args, **kwargs):
        was_created = not bool(self.pk)
        super().save(*args, **kwargs)

        if was_created:
            self.build_initial_data()

    @property
    def plugin_list(self) -> list:
        if not self.plugins:
            return []
        return self.plugins.split(",")

    def set_plugins(self, modules: list) -> None:
        """
        This method is not @plugin_list.setter to make the side effects more visible.
        It will call installed() on all plugins that were not active before, and
        uninstalled() on all plugins that are not active anymore.
        """
        plugins_active = set(self.plugin_list)
        plugins_available = {
            p.module: p
            for p in get_all_plugins(self)
            if not p.name.startswith(".") and getattr(p, "visible", True)
        }

        enable = set(modules) & (set(plugins_available) - plugins_active)
        disable = plugins_active - set(modules)

        for module in enable:
            if hasattr(plugins_available[module].app, "installed"):
                plugins_available[module].app.installed(self)
        for module in disable:
            if hasattr(plugins_available[module].app, "uninstalled"):
                plugins_available[module].app.uninstalled(self)

        self.plugins = ",".join(modules)

    def enable_plugin(self, module: str) -> None:
        """Enables a plugin. If the given plugin is available and was not in the list of
        active plugins, it will be added and installed() will be called."""
        plugins_active = self.plugin_list
        if module not in plugins_active:
            plugins_active.append(module)
            self.set_plugins(plugins_active)

    def disable_plugin(self, module: str) -> None:
        """Disables a plugin. If the given plugin is in the list of active
        plugins, it will be removed and uninstall() will be called."""
        plugins_active = self.plugin_list
        if module in plugins_active:
            plugins_active.remove(module)
            self.set_plugins(plugins_active)

    def get_primary_color(self):
        return self.primary_color or settings.DEFAULT_EVENT_PRIMARY_COLOR

    def _get_default_submission_type(self):
        from pretalx.submission.models import SubmissionType

        sub_type = SubmissionType.objects.filter(event=self).first()
        if not sub_type:
            sub_type = SubmissionType.objects.create(event=self, name="Talk")
        return sub_type

    @cached_property
    def fixed_templates(self) -> list:
        return [
            self.accept_template,
            self.ack_template,
            self.reject_template,
            self.update_template,
            self.question_template,
        ]

    def build_initial_data(self):
        from pretalx.mail.default_templates import (
            ACCEPT_TEXT,
            ACK_TEXT,
            GENERIC_SUBJECT,
            QUESTION_SUBJECT,
            QUESTION_TEXT,
            REJECT_TEXT,
            UPDATE_SUBJECT,
            UPDATE_TEXT,
        )
        from pretalx.mail.models import MailTemplate
        from pretalx.submission.models import CfP

        if not hasattr(self, "cfp"):
            CfP.objects.create(
                event=self, default_type=self._get_default_submission_type()
            )

        if not self.schedules.filter(version__isnull=True).exists():
            from pretalx.schedule.models import Schedule

            Schedule.objects.create(event=self)

        self.accept_template = self.accept_template or MailTemplate.objects.create(
            event=self, subject=GENERIC_SUBJECT, text=ACCEPT_TEXT
        )
        self.ack_template = self.ack_template or MailTemplate.objects.create(
            event=self, subject=GENERIC_SUBJECT, text=ACK_TEXT
        )
        self.reject_template = self.reject_template or MailTemplate.objects.create(
            event=self, subject=GENERIC_SUBJECT, text=REJECT_TEXT
        )
        self.update_template = self.update_template or MailTemplate.objects.create(
            event=self, subject=UPDATE_SUBJECT, text=UPDATE_TEXT
        )
        self.question_template = self.question_template or MailTemplate.objects.create(
            event=self, subject=QUESTION_SUBJECT, text=QUESTION_TEXT
        )

        if not self.review_phases.all().exists():
            from pretalx.submission.models import ReviewPhase

            cfp_deadline = self.cfp.deadline
            r = ReviewPhase.objects.create(
                event=self,
                name=_("Review"),
                start=cfp_deadline,
                end=self.datetime_from - relativedelta(months=-3),
                is_active=bool(not cfp_deadline or cfp_deadline < now()),
                position=0,
            )
            ReviewPhase.objects.create(
                event=self,
                name=_("Selection"),
                start=r.end,
                is_active=False,
                position=1,
                can_review=False,
                can_see_other_reviews="always",
                can_change_submission_state=True,
            )
        if not self.score_categories.all().exists():
            from pretalx.submission.models import ReviewScore, ReviewScoreCategory

            category = ReviewScoreCategory.objects.create(
                event=self,
                name=str(_("Score")),
            )
            ReviewScore.objects.create(
                category=category,
                value=0,
                label=str(_("No")),
            )
            ReviewScore.objects.create(
                category=category,
                value=1,
                label=str(_("Maybe")),
            )
            ReviewScore.objects.create(
                category=category,
                value=2,
                label=str(_("Yes")),
            )
        self.save()

    build_initial_data.alters_data = True

    def _delete_mail_templates(self):
        for template in self.template_names:
            setattr(self, template, None)
        self.save()
        self.mail_templates.all().delete()

    _delete_mail_templates.alters_data = True

    @scopes_disabled()
    def copy_data_from(self, other_event, skip_attributes=None):
        from pretalx.orga.signals import event_copy_data

        delta = self.date_from - other_event.date_from

        clonable_attributes = [
            "locale",
            "locale_array",
            "primary_color",
            "timezone",
            "email",
            "plugins",
            "feature_flags",
            "display_settings",
            "review_settings",
            "content_locale_array",
            "landing_page_text",
            "featured_sessions_text",
        ]
        if skip_attributes:
            clonable_attributes = [
                a for a in clonable_attributes if a not in skip_attributes
            ]
        for attribute in clonable_attributes:
            setattr(self, attribute, getattr(other_event, attribute))
        self.save()

        self._delete_mail_templates()
        self.submission_types.exclude(pk=self.cfp.default_type_id).delete()
        copied_templates = []
        for template in self.template_names:
            new_template = getattr(other_event, template)
            copied_templates.append(new_template.pk)
            new_template.pk = None
            new_template.event = self
            new_template.save()
            setattr(self, template, new_template)
        # We copy non-default templates separately
        for template in (
            other_event.mail_templates.all()
            .filter(is_auto_created=False)
            .exclude(pk__in=copied_templates)
        ):
            template.pk = None
            template.event = self
            template.save()
        submission_type_map = {}
        for submission_type in other_event.submission_types.all():
            submission_type_map[submission_type.pk] = submission_type
            is_default = submission_type == other_event.cfp.default_type
            submission_type.pk = None
            submission_type.event = self
            submission_type.save()
            if is_default:
                old_default = self.cfp.default_type
                self.cfp.default_type = submission_type
                self.cfp.save()
                old_default.delete()
        track_map = {}
        for track in other_event.tracks.all():
            track_map[track.pk] = track
            track.pk = None
            track.event = self
            track.save()
        question_map = {}
        for question in other_event.questions.all():
            question_map[question.pk] = question
            options = question.options.all()
            tracks = question.tracks.all().values_list("pk", flat=True)
            types = question.submission_types.all().values_list("pk", flat=True)
            question.pk = None
            question.event = self
            question.save()
            question.tracks.set([])
            question.submission_types.set([])
            for option in options:
                option.pk = None
                option.question = question
                option.save()
            for track in tracks:
                question.tracks.add(track_map.get(track))
            for stype in types:
                question.submission_types.add(submission_type_map.get(stype))

        information_map = {}
        for information in other_event.information.all():
            information_map[information.pk] = information
            tracks = information.limit_tracks.all().values_list("pk", flat=True)
            types = information.limit_types.all().values_list("pk", flat=True)
            information.pk = None
            information.event = self
            information.save()
            information.limit_tracks.set([])
            information.limit_types.set([])
            for track in tracks:
                information.limit_tracks.add(track_map.get(track))
            for stype in types:
                information.limit_types.add(submission_type_map.get(stype))

        self.review_phases.all().delete()
        for review_phase in other_event.review_phases.all():
            review_phase.pk = None
            review_phase.event = self
            review_phase.is_active = False
            if review_phase.start:
                review_phase.start += delta
            if review_phase.end:
                review_phase.end += delta
            review_phase.save()

        self.score_categories.all().delete()
        for score_category in other_event.score_categories.all():
            scores = list(score_category.scores.all())
            tracks = list(score_category.limit_tracks.all())
            score_category.pk = None
            score_category.event = self
            score_category.save()
            score_category.limit_tracks.set([])
            for track in tracks:
                score_category.limit_tracks.add(track_map.get(track))
            for score in scores:
                score.pk = None
                score.category = score_category
                score.save()

        for s in other_event.settings._objects.all():
            if s.value.startswith("file://"):
                continue
            s.object = self
            s.pk = None
            s.save()
        self.settings.flush()
        self.cfp.copy_data_from(other_event.cfp, skip_attributes=skip_attributes)
        event_copy_data.send(
            sender=self,
            other=other_event.slug,
            question_map=question_map,
            track_map=track_map,
            submission_type_map=submission_type_map,
            speaker_information_map=information_map,
        )
        self.build_initial_data()  # make sure we get a functioning event

    copy_data_from.alters_data = True

    @cached_property
    def pending_mails(self) -> int:
        """The amount of currently unsent.

        :class:`~pretalx.mail.models.QueuedMail` objects.
        """
        return self.queued_mails.filter(sent__isnull=True).count()

    @cached_property
    def wip_schedule(self):
        """Returns the latest unreleased.

        :class:`~pretalx.schedule.models.schedule.Schedule`.

        :retval: :class:`~pretalx.schedule.models.schedule.Schedule`
        """
        try:
            schedule, _ = self.schedules.get_or_create(version__isnull=True)
        except MultipleObjectsReturned:
            # No idea how this happens – a race condition due to transaction weirdness?
            from pretalx.schedule.models import TalkSlot

            schedules = list(self.schedules.filter(version__isnull=True))
            schedule = schedules[0]
            # It's only ever been two so far, but while we're being resilient …
            for dupe in schedules[1:]:
                TalkSlot.objects.filter(schedule=dupe).delete()
                dupe.delete()
        return schedule

    @cached_property
    def current_schedule(self):
        """Returns the latest released.

        :class:`~pretalx.schedule.models.schedule.Schedule`, or ``None`` before
        the first release.
        """
        return (
            self.schedules.order_by("-published")
            .filter(published__isnull=False)
            .first()
        )

    @cached_property
    def duration(self):
        return (self.date_to - self.date_from).days + 1

    def get_mail_backend(self, force_custom: bool = False) -> BaseEmailBackend:
        from pretalx.common.mail import CustomSMTPBackend

        if self.mail_settings["smtp_use_custom"] or force_custom:
            return CustomSMTPBackend(
                host=self.mail_settings["smtp_host"],
                port=self.mail_settings["smtp_port"],
                username=self.mail_settings["smtp_username"],
                password=self.mail_settings["smtp_password"],
                use_tls=self.mail_settings["smtp_use_tls"],
                use_ssl=self.mail_settings["smtp_use_ssl"],
                fail_silently=False,
            )
        return get_connection(fail_silently=False)

    @cached_property
    def event(self):
        return self

    @cached_property
    def teams(self):
        """Returns all :class:`~pretalx.event.models.organiser.Team` objects
        that concern this event."""
        from .organiser import Team

        return Team.objects.filter(
            models.Q(limit_events__in=[self]) | models.Q(all_events=True),
            organiser=self.organiser,
        )

    @cached_property
    def reviewers(self):
        from pretalx.person.models import User

        return User.objects.filter(
            teams__in=self.teams.filter(is_reviewer=True)
        ).distinct()

    @cached_property
    def datetime_from(self) -> dt.datetime:
        """The localised datetime of the event start date.

        :rtype: datetime
        """
        return make_aware(
            dt.datetime.combine(self.date_from, dt.time(hour=0, minute=0, second=0)),
            self.tz,
        )

    @cached_property
    def datetime_to(self) -> dt.datetime:
        """The localised datetime of the event end date.

        :rtype: datetime
        """
        return make_aware(
            dt.datetime.combine(self.date_to, dt.time(hour=23, minute=59, second=59)),
            self.tz,
        )

    @cached_property
    def tz(self):
        return zoneinfo.ZoneInfo(self.timezone)

    @cached_property
    def reviews(self):
        from pretalx.submission.models import Review

        return Review.objects.filter(submission__event=self)

    @cached_property
    def active_review_phase(self):
        phase = self.review_phases.filter(is_active=True).first()
        if not phase and not self.review_phases.all().exists():
            from pretalx.submission.models import ReviewPhase

            cfp_deadline = self.cfp.deadline
            phase = ReviewPhase.objects.create(
                event=self,
                name=_("Review"),
                start=cfp_deadline,
                end=self.datetime_from - relativedelta(months=-3),
                is_active=bool(cfp_deadline),
                can_see_other_reviews="after_review",
                can_see_speaker_names=True,
            )
        return phase

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
        old_position = old_phase.position if old_phase else -1
        future_phases = future_phases.filter(position__gt=old_position)
        next_phase = future_phases.order_by("position").first()
        if not (
            next_phase
            and (
                (next_phase.start and next_phase.start <= _now) or not next_phase.start
            )
        ):
            return old_phase
        next_phase.activate()
        return next_phase

    update_review_phase.alters_data = True

    @cached_property
    def talks(self):
        """Returns a queryset of all.

        :class:`~pretalx.submission.models.submission.Submission` object in the
        current released schedule.
        """
        from pretalx.submission.models.submission import Submission

        if self.current_schedule:
            return (
                self.submissions.filter(
                    slots__in=self.current_schedule.talks.filter(is_visible=True)
                )
                .select_related("submission_type")
                .prefetch_related("speakers")
            )
        return Submission.objects.none()

    @cached_property
    def speakers(self):
        """Returns a queryset of all speakers (of type.

        :class:`~pretalx.person.models.user.User`) visible in the current
        released schedule.
        """
        from pretalx.person.models import User

        return User.objects.filter(submissions__in=self.talks).order_by("id").distinct()

    @cached_property
    def submitters(self):
        """Returns a queryset of all :class:`~pretalx.person.models.user.User`
        objects who have submitted to this event.

        Ignores users who have deleted all of their submissions.
        """
        from pretalx.person.models import User

        return (
            User.objects.filter(submissions__in=self.submissions.all())
            .prefetch_related("submissions")
            .order_by("id")
            .distinct()
        )

    @cached_property
    def cfp_flow(self):
        from pretalx.cfp.flow import CfPFlow

        return CfPFlow(self)

    def get_date_range_display(self) -> str:
        """Returns the localised, prettily formatted date range for this event.

        E.g. as long as the event takes place within the same month, the
        month is only named once.
        """
        return daterange(self.date_from, self.date_to)

    def release_schedule(
        self, name: str, user=None, notify_speakers: bool = False, comment: str = None
    ):
        """Releases a new :class:`~pretalx.schedule.models.schedule.Schedule`
        by finalising the current WIP schedule.

        :param name: The new version name
        :param user: The :class:`~pretalx.person.models.user.User` executing the release
        :param notify_speakers: Generate emails for all speakers with changed slots.
        :param comment: Public comment for the release
        :type user: :class:`~pretalx.person.models.user.User`
        """
        self.wip_schedule.freeze(
            name=name, user=user, notify_speakers=notify_speakers, comment=comment
        )

    release_schedule.alters_data = True

    def send_orga_mail(self, text, stats=False):
        from django.utils.translation import override

        from pretalx.mail.models import QueuedMail

        context = {
            "event_dashboard": self.orga_urls.base.full(),
            "event_review": self.orga_urls.reviews.full(),
            "event_schedule": self.orga_urls.schedule.full(),
            "event_submissions": self.orga_urls.submissions.full(),
            "event_team": self.orga_urls.team_settings.full(),
            "submission_count": self.submissions.all().count(),
        }
        if stats:
            context.update(
                {
                    "talk_count": self.current_schedule.talks.filter(
                        is_visible=True
                    ).count(),
                    "review_count": self.reviews.count(),
                    "schedule_count": self.schedules.count() - 1,
                    "mail_count": self.queued_mails.filter(sent__isnull=False).count(),
                }
            )
        with override(self.locale):
            QueuedMail(
                subject=_("News from your content system"),
                text=str(text).format(**context),
                to=self.email,
                locale=self.locale,
            ).send()

    @transaction.atomic
    def shred(self):
        """Irrevocably deletes an event and all related data."""
        from pretalx.common.models import ActivityLog
        from pretalx.person.models import SpeakerProfile
        from pretalx.schedule.models import TalkSlot
        from pretalx.submission.models import (
            Answer,
            AnswerOption,
            Feedback,
            Question,
            Resource,
            Submission,
        )

        deletion_order = [
            (self.logged_actions(), False),
            (self.queued_mails.all(), False),
            (self.cfp, False),
            (self.mail_templates.all(), False),
            (self.information.all(), True),
            (TalkSlot.objects.filter(schedule__event=self), False),
            (Feedback.objects.filter(talk__event=self), False),
            (Resource.objects.filter(submission__event=self), True),
            (Answer.objects.filter(question__event=self), True),
            (AnswerOption.objects.filter(question__event=self), False),
            (Question.all_objects.filter(event=self), False),
            (Submission.all_objects.filter(event=self), True),
            (self.tracks.all(), False),
            (self.tags.all(), False),
            (self.submission_types.all(), False),
            (self.schedules.all(), False),
            (SpeakerProfile.objects.filter(event=self), False),
            (self.rooms.all(), False),
            (ActivityLog.objects.filter(event=self), False),
            (self, False),
        ]

        self._delete_mail_templates()
        for entry, detail in deletion_order:
            if detail:
                for obj in entry:
                    if isinstance(obj, Submission):
                        obj.delete(force=True)
                    else:
                        obj.delete()
            else:
                entry.delete()

    shred.alters_data = True
