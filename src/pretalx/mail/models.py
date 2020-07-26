from copy import deepcopy

import bleach
import markdown
from django.db import models, transaction
from django.template.loader import get_template
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.utils.translation import override
from django_scopes import ScopedManager
from i18nfield.fields import I18nCharField, I18nTextField

from pretalx.common.mail import SendMailException
from pretalx.common.mixins import LogMixin
from pretalx.common.templatetags.rich_text import ALLOWED_TAGS
from pretalx.common.urls import EventUrls


class MailTemplate(LogMixin, models.Model):
    """MailTemplates can be used to create.

    :class:`~pretalx.mail.models.QueuedMail` objects.

    The process does not come with variable substitution except for
    special cases, for now.
    """

    event = models.ForeignKey(
        to="event.Event", on_delete=models.PROTECT, related_name="mail_templates",
    )
    subject = I18nCharField(max_length=200, verbose_name=_("Subject"),)
    text = I18nTextField(verbose_name=_("Text"),)
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

    objects = ScopedManager(event="event")

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
        skip_queue: bool = False,
        commit: bool = True,
        submission=None,
        full_submission_content: bool = False,
    ):
        """Creates a :class:`~pretalx.mail.models.QueuedMail` object from a
        MailTemplate.

        :param user: Either a :class:`~pretalx.person.models.user.User` or an
            email address as a string.
        :param event: The event to which this email belongs. May be ``None``.
        :param locale: The locale will be set via the event and the recipient,
            but can be overridden with this parameter.
        :param context: Context to be used when rendering the template.
        :param skip_queue: Send directly without saving. Use with caution, as
            it removes any logging and traces.
        :param commit: Set ``False`` to return an unsaved object.
        :param submission: Pass a submission if one is related to the mail.
            Will be used to generate context.
        :param full_submission_content: Attach the complete submission with
            all its fields to the email.
        """
        from pretalx.person.models import User

        if isinstance(user, str):
            address = user
            users = None
        elif isinstance(user, User):
            address = None
            users = [user]
        else:
            raise TypeError(
                "First argument to to_mail must be a string or a User, not "
                + str(type(user))
            )
        if users and (not commit or skip_queue):
            address = ",".join(user.email for user in users)
            users = None

        with override(locale):
            context = context or dict()
            try:
                subject = str(self.subject).format(**context)
                text = str(self.text).format(**context)
                if submission and full_submission_content:
                    text += "\n\n\n***********\n\n" + str(
                        _("Full submission content:\n\n")
                    )
                    text += submission.get_content_for_mail()
            except KeyError as e:
                raise SendMailException(
                    f"Experienced KeyError when rendering email text: {str(e)}"
                )

            if len(subject) > 200:
                subject = subject[:198] + "…"

            mail = QueuedMail(
                event=self.event,
                to=address,
                reply_to=self.reply_to,
                bcc=self.bcc,
                subject=subject,
                text=text,
            )
            if skip_queue:
                mail.send()
            elif commit:
                mail.save()
                if users:
                    mail.to_users.set(users)
        return mail

    to_mail.alters_data = True


class QueuedMail(LogMixin, models.Model):
    """Emails in pretalx are rarely sent directly, hence the name QueuedMail.

    This mechanism allows organisers to make sure they send out the right
    content, and to include personal changes in emails.

    :param sent_at: ``None`` if the mail has not been sent yet.
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
    to = models.CharField(
        max_length=1000,
        verbose_name=_("To"),
        help_text=_("One email address or several addresses separated by commas."),
        null=True,
        blank=True,
    )
    to_users = models.ManyToManyField(to="person.User", related_name="mails",)
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
    subject = models.CharField(max_length=200, verbose_name=_("Subject"))
    text = models.TextField(verbose_name=_("Text"))
    sent = models.DateTimeField(null=True, blank=True, verbose_name=_("Sent at"))

    objects = ScopedManager(event="event")

    class urls(EventUrls):
        base = edit = "{self.event.orga_urls.mail}{self.pk}/"
        delete = "{base}delete"
        send = "{base}send"
        copy = "{base}copy"

    def __str__(self):
        """Help with debugging."""
        sent = self.sent.isoformat() if self.sent else None
        return f"OutboxMail(to={self.to}, subject={self.subject}, sent={sent})"

    @classmethod
    def make_html(cls, text, event=None):
        body_md = bleach.linkify(
            bleach.clean(markdown.markdown(text), tags=ALLOWED_TAGS), parse_email=True,
        )
        html_context = {
            "body": body_md,
            "event": event,
            "color": (event.primary_color if event else "") or "#3aa57c",
        }
        return get_template("mail/mailwrapper.html").render(html_context)

    @classmethod
    def make_text(cls, text, event=None):
        if not event or not event.settings.mail_signature:
            return text
        sig = event.settings.mail_signature
        if not sig.strip().startswith("-- "):
            sig = f"-- \n{sig}"
        return f"{text}\n{sig}"

    @classmethod
    def make_subject(cls, text, event=None):
        if not event or not event.settings.mail_subject_prefix:
            return text
        prefix = event.settings.mail_subject_prefix
        if not (prefix.startswith("[") and prefix.endswith("]")):
            prefix = f"[{prefix}]"
        return f"{prefix} {text}"

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
        text = self.make_text(self.text, event=has_event)
        body_html = self.make_html(text)

        from pretalx.common.mail import mail_send_task

        to = self.to.split(",") if self.to else []
        if self.id:
            to += [user.email for user in self.to_users.all()]
        mail_send_task.apply_async(
            kwargs={
                "to": to,
                "subject": self.make_subject(self.subject, event=has_event),
                "body": text,
                "html": body_html,
                "reply_to": (self.reply_to or "").split(","),
                "event": self.event.pk if has_event else None,
                "cc": (self.cc or "").split(","),
                "bcc": (self.bcc or "").split(","),
            }
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
