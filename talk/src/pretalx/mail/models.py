from copy import deepcopy

from django.conf import settings
from django.db import models, transaction
from django.template.loader import get_template
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.utils.translation import override, pgettext_lazy
from i18nfield.fields import I18nCharField, I18nTextField

from pretalx.common.exceptions import SendMailException
from pretalx.common.models.mixins import PretalxModel
from pretalx.common.urls import EventUrls
from pretalx.mail.context import get_mail_context
from pretalx.mail.signals import queuedmail_post_send, queuedmail_pre_send


def get_prefixed_subject(event, subject):
    if not (prefix := event.mail_settings["subject_prefix"]):
        return subject
    if not (prefix.startswith("[") and prefix.endswith("]")):
        prefix = f"[{prefix}]"
    return f"{prefix} {subject}"


class MailTemplateRoles(models.TextChoices):
    NEW_SUBMISSION = "submission.new", _("Acknowledge proposal submission")
    NEW_SUBMISSION_INTERNAL = "submission.new.internal", _(
        "New proposal (organiser notification)"
    )
    SUBMISSION_ACCEPT = "submission.state.accepted", _("Proposal accepted")
    SUBMISSION_REJECT = "submission.state.rejected", _("Proposal rejected")
    NEW_SPEAKER_INVITE = "speaker.invite", _(
        "Add a speaker to a proposal (new account)"
    )
    EXISTING_SPEAKER_INVITE = "speaker.invite.existing", _(
        "Add a speaker to a proposal (existing account)"
    )
    QUESTION_REMINDER = "question.reminder", _("Unanswered questions reminder")
    NEW_SCHEDULE = "schedule.new", _("New schedule published")


class MailTemplate(PretalxModel):
    """MailTemplates can be used to create.

    :class:`~pretalx.mail.models.QueuedMail` objects.

    The process does not come with variable substitution except for
    special cases, for now.
    """

    event = models.ForeignKey(
        to="event.Event",
        on_delete=models.PROTECT,
        related_name="mail_templates",
    )
    role = models.CharField(
        choices=MailTemplateRoles.choices,
        max_length=30,
        null=True,
        default=None,
    )
    subject = I18nCharField(
        max_length=200,
        verbose_name=pgettext_lazy("email subject", "Subject"),
    )
    text = I18nTextField(
        verbose_name=_("Text"),
    )
    reply_to = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name=_("Reply-To"),
        help_text=_(
            "Change the Reply-To address if you do not want to use the default organiser address"
        ),
    )
    bcc = models.CharField(
        max_length=1000,
        blank=True,
        null=True,
        verbose_name=_("BCC"),
        help_text=_(
            "Enter comma separated addresses. Will receive a blind copy of every mail sent from this template. This may be a LOT!"
        ),
    )
    # Auto-created templates are created when mass emails are sent out. They are only used to re-create similar
    # emails, and are never shown in a list of email templates or anywhere else.
    is_auto_created = models.BooleanField(default=False)

    class Meta:
        unique_together = (("event", "role"),)

    class urls(EventUrls):
        base = edit = "{self.event.orga_urls.mail_templates}{self.pk}/"
        delete = "{base}delete"

    def __str__(self):
        """Help with debugging."""
        return f"MailTemplate(event={self.event.slug}, subject={self.subject})"

    def to_mail(
        self,
        user,
        event,
        locale: str = None,
        context: dict = None,
        context_kwargs: dict = None,
        skip_queue: bool = False,
        commit: bool = True,
        allow_empty_address: bool = False,
        submissions: list = None,
        attachments: list = False,
    ):
        """Creates a :class:`~pretalx.mail.models.QueuedMail` object from a
        MailTemplate.

        :param user: Either a :class:`~pretalx.person.models.user.User` or an
            email address as a string.
        :param submissions: A list of submissions to which this email belongs.
            This is handled as an addition to any `submission` object present
            in ``context_kwargs``.
        :param event: The event to which this email belongs. May be ``None``.
        :param locale: The locale will be set via the event and the recipient,
            but can be overridden with this parameter.
        :param context: Context to be used when rendering the template. Merged with
            all context available via get_mail_context.
        :param context_kwargs: Passed to get_mail_context to retrieve the correct
            context when rendering the template.
        :param skip_queue: Send directly. If combined with commit=False, this will
            remove any logging and traces.
        :param commit: Set ``False`` to return an unsaved object.
        """
        from pretalx.person.models import User

        if isinstance(user, str):
            address = user
            users = None
        elif isinstance(user, User):
            address = None
            users = [user]
            locale = locale or user.locale
        elif not user and allow_empty_address:
            address = None
            users = None
        else:
            raise TypeError(
                "First argument to to_mail must be a string or a User, not "
                + str(type(user))
            )
        if users and not commit:
            address = ",".join(user.email for user in users)
            users = None
        event = event or self.event

        with override(locale):
            context_kwargs = context_kwargs or {}
            context_kwargs["event"] = event
            default_context = get_mail_context(**context_kwargs)
            default_context.update(context or {})
            context = default_context
            try:
                subject = str(self.subject).format(**context)
                text = str(self.text).format(**context)
            except KeyError as e:
                raise SendMailException(
                    f"Experienced KeyError when rendering email text: {str(e)}"
                )

            if len(subject) > 200:
                subject = subject[:198] + "…"

            mail = QueuedMail(
                event=event,
                template=self,
                to=address,
                reply_to=self.reply_to,
                bcc=self.bcc,
                subject=subject,
                text=text,
                locale=locale,
                attachments=attachments,
            )
            if commit:
                mail.save()
                submissions = set(submissions or [])
                if submission := context_kwargs.get("submission"):
                    submissions.add(submission)
                if submissions:
                    mail.submissions.set(submissions)
                if users:
                    mail.to_users.set(users)
            if skip_queue:
                mail.send()
        return mail

    to_mail.alters_data = True


class QueuedMail(PretalxModel):
    """Emails in pretalx are rarely sent directly, hence the name QueuedMail.

    This mechanism allows organisers to make sure they send out the right
    content, and to include personal changes in emails.

    :param sent: ``None`` if the mail has not been sent yet.
    :param to_users: All known users to whom this email is addressed.
    :param to: A comma-separated list of email addresses to whom this email
        is addressed. Does not contain any email addresses known to belong
        to users.
    """

    event = models.ForeignKey(
        to="event.Event",
        on_delete=models.PROTECT,
        related_name="queued_mails",
        null=True,
        blank=True,
    )
    template = models.ForeignKey(
        to=MailTemplate,
        related_name="mails",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    to = models.CharField(
        max_length=1000,
        verbose_name=_("To"),
        help_text=_("One email address or several addresses separated by commas."),
        null=True,
        blank=True,
    )
    to_users = models.ManyToManyField(
        to="person.User",
        related_name="mails",
    )
    reply_to = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
        verbose_name=_("Reply-To"),
        help_text=_("By default, the organiser address is used as Reply-To."),
    )
    cc = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
        verbose_name=_("CC"),
        help_text=_("One email address or several addresses separated by commas."),
    )
    bcc = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
        verbose_name=_("BCC"),
        help_text=_("One email address or several addresses separated by commas."),
    )
    subject = models.CharField(
        max_length=200, verbose_name=pgettext_lazy("email subject", "Subject")
    )
    text = models.TextField(verbose_name=_("Text"))
    sent = models.DateTimeField(null=True, blank=True, verbose_name=_("Sent at"))
    locale = models.CharField(max_length=32, null=True, blank=True)
    attachments = models.JSONField(default=None, null=True, blank=True)
    submissions = models.ManyToManyField(
        to="submission.Submission",
        related_name="mails",
    )

    class urls(EventUrls):
        base = edit = "{self.event.orga_urls.mail}{self.pk}/"
        delete = "{base}delete"
        send = "{base}send"
        copy = "{base}copy"

    def __str__(self):
        """Help with debugging."""
        sent = self.sent.isoformat() if self.sent else None
        return f"OutboxMail(to={self.to}, subject={self.subject}, sent={sent})"

    def make_html(self):
        from pretalx.common.templatetags.rich_text import render_markdown_abslinks

        event = getattr(self, "event", None)
        sig = None
        if event:
            sig = event.mail_settings["signature"]
            if sig.strip().startswith("-- "):
                sig = sig.strip()[3:].strip()
        body_md = render_markdown_abslinks(self.text)
        html_context = {
            "body": body_md,
            "event": event,
            "color": (event.primary_color if event else "")
            or settings.DEFAULT_EVENT_PRIMARY_COLOR,
            "locale": self.locale,
            "rtl": self.locale in settings.LANGUAGES_RTL,
            "subject": self.subject,
            "signature": sig,
        }
        return get_template("mail/mailwrapper.html").render(html_context)

    def make_text(self):
        event = getattr(self, "event", None)
        if not event or not event.mail_settings["signature"]:
            return self.text
        sig = event.mail_settings["signature"]
        if not sig.strip().startswith("-- "):
            sig = f"-- \n{sig}"
        return f"{self.text}\n{sig}"

    @cached_property
    def prefixed_subject(self):
        event = getattr(self, "event", None)
        if not event:
            return self.subject
        return get_prefixed_subject(event, self.subject)

    @transaction.atomic
    def send(self, requestor=None, orga: bool = True):
        """Sends an email.

        :param requestor: The user issuing the command. Used for logging.
        :type requestor: :class:`~pretalx.person.models.user.User`
        :param orga: Was this email sent as by a privileged user?
        """
        if self.sent:
            raise Exception(
                _("This mail has been sent already. It cannot be sent again.")
            )

        has_event = getattr(self, "event", None)

        to = self.to.split(",") if self.to else []
        if self.id:
            to += [user.email for user in self.to_users.all()]
            if has_event:
                queuedmail_pre_send.send_robust(
                    sender=self.event,
                    mail=self,
                )

        if self.sent is not None:
            # The pre_send signal must have handled the sending already,
            # so there is nothing left for us to do.
            return

        from pretalx.common.mail import mail_send_task

        text = self.make_text()
        body_html = self.make_html()
        mail_send_task.apply_async(
            kwargs={
                "to": to,
                "subject": self.prefixed_subject,
                "body": text,
                "html": body_html,
                "reply_to": (self.reply_to or "").split(","),
                "event": self.event.pk if has_event else None,
                "cc": (self.cc or "").split(","),
                "bcc": (self.bcc or "").split(","),
                "attachments": self.attachments,
            },
            ignore_result=True,
        )
        self.sent = now()

        if self.pk:
            self.log_action(
                "pretalx.mail.sent",
                person=requestor,
                orga=orga,
                data={
                    "to_users": [(user.pk, user.email) for user in self.to_users.all()]
                },
            )
            self.save()
            queuedmail_post_send.send(
                sender=self.event,
                mail=self,
            )

    send.alters_data = True

    def copy_to_draft(self):
        """Copies an already sent email to a new object and adds it to the
        outbox."""
        new_mail = deepcopy(self)
        new_mail.pk = None
        new_mail.sent = None
        new_mail.save()
        for user in self.to_users.all():
            new_mail.to_users.add(user)
        return new_mail

    copy_to_draft.alters_data = True
