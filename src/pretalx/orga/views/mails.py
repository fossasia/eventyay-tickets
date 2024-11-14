import bleach
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.functional import cached_property
from django.utils.html import escape
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext_lazy
from django.views.generic import FormView, ListView, TemplateView, View
from django_context_decorator import context

from pretalx.common.language import language
from pretalx.common.mail import TolerantDict
from pretalx.common.text.phrases import phrases
from pretalx.common.views import CreateOrUpdateView
from pretalx.common.views.mixins import (
    ActionConfirmMixin,
    ActionFromUrl,
    EventPermissionRequired,
    Filterable,
    PaginationMixin,
    PermissionRequired,
    Sortable,
)
from pretalx.mail.models import MailTemplate, QueuedMail, get_prefixed_subject
from pretalx.orga.forms.mails import (
    DraftRemindersForm,
    MailDetailForm,
    MailTemplateForm,
    WriteSessionMailForm,
    WriteTeamsMailForm,
)


class OutboxList(
    EventPermissionRequired, Sortable, Filterable, PaginationMixin, ListView
):
    model = QueuedMail
    context_object_name = "mails"
    template_name = "orga/mails/outbox_list.html"
    default_sort_field = "-pk"
    default_filters = (
        "to__icontains",
        "subject__icontains",
        "to_users__name__icontains",
        "to_users__email__icontains",
    )
    sortable_fields = ("to", "subject", "pk")
    paginate_by = 25
    permission_required = "orga.view_mails"

    def get_queryset(self):
        qs = (
            self.request.event.queued_mails.prefetch_related(
                "to_users", "submissions", "submissions__track"
            )
            .filter(sent__isnull=True)
            .order_by("-id")
        )
        qs = self.filter_queryset(qs)
        return self.sort_queryset(qs)

    @context
    @cached_property
    def show_tracks(self):
        return self.request.event.get_feature_flag("use_tracks")

    @context
    @cached_property
    def is_filtered(self):
        return (
            self.get_queryset().count()
            != self.request.event.queued_mails.filter(sent__isnull=True).count()
        )


class SentMail(
    EventPermissionRequired, Sortable, Filterable, PaginationMixin, ListView
):
    model = QueuedMail
    context_object_name = "mails"
    template_name = "orga/mails/sent_list.html"
    default_filters = (
        "to__icontains",
        "subject__icontains",
        "to_users__name__icontains",
        "to_users__email__icontains",
    )
    default_sort_field = "-sent"
    sortable_fields = ("to", "subject", "sent")
    paginate_by = 25
    permission_required = "orga.view_mails"

    def get_queryset(self):
        qs = (
            self.request.event.queued_mails.prefetch_related(
                "to_users", "submissions", "submissions__track"
            )
            .filter(sent__isnull=False)
            .order_by("-sent")
        )
        qs = self.filter_queryset(qs)
        return self.sort_queryset(qs)

    @context
    @cached_property
    def show_tracks(self):
        return self.request.event.get_feature_flag("use_tracks")


class OutboxSend(ActionConfirmMixin, OutboxList):
    permission_required = "orga.send_mails"
    action_object_name = ""
    action_confirm_label = phrases.base.send
    action_confirm_color = "success"
    action_confirm_icon = "envelope"

    @context
    def question(self):
        return _("Do you really want to send {count} mails?").format(
            count=self.queryset.count()
        )

    def action_title(self):
        return _("Send emails")

    def action_text(self):
        return self.question()

    @property
    def action_back_url(self):
        return self.request.event.orga_urls.outbox

    def dispatch(self, request, *args, **kwargs):
        if "pk" in self.kwargs:
            try:
                mail = self.request.event.queued_mails.get(pk=self.kwargs.get("pk"))
            except QueuedMail.DoesNotExist:
                messages.error(
                    request,
                    _(
                        "This mail either does not exist or cannot be sent because it was sent already."
                    ),
                )
                return redirect(self.request.event.orga_urls.outbox)
            if mail.sent:
                messages.error(request, _("This mail had been sent already."))
            else:
                mail.send(requestor=self.request.user)
                messages.success(request, _("The mail has been sent."))
            return redirect(self.request.event.orga_urls.outbox)
        return super().dispatch(request, *args, **kwargs)

    @cached_property
    def queryset(self):
        pks = self.request.GET.get("pks") or ""
        if pks:
            return self.request.event.queued_mails.filter(sent__isnull=True).filter(
                pk__in=pks.split(",")
            )
        return self.get_queryset()

    def post(self, request, *args, **kwargs):
        mails = self.queryset
        count = mails.count()
        for mail in mails:
            mail.send(requestor=self.request.user)
        messages.success(
            request, _("{count} mails have been sent.").format(count=count)
        )
        return redirect(self.request.event.orga_urls.outbox)


class MailDelete(PermissionRequired, ActionConfirmMixin, TemplateView):
    permission_required = "orga.purge_mails"
    action_object_name = ""

    def get_permission_object(self):
        return self.request.event

    @cached_property
    def queryset(self):
        mail = self.request.event.queued_mails.filter(
            sent__isnull=True, pk=self.kwargs.get("pk")
        )
        if "all" in self.request.GET and mail:
            return self.request.event.queued_mails.filter(
                sent__isnull=True, template=mail.first().template
            )
        return mail

    def action_text(self):
        return self.question()

    @property
    def action_back_url(self):
        return self.request.event.orga_urls.outbox

    @context
    def question(self):
        count = len(self.queryset)
        return str(
            ngettext_lazy(
                "Do you really want to delete this mail?",
                "Do you really want to purge {count} mails?",
                count,
            )
        ).format(count=count)

    def post(self, request, *args, **kwargs):
        mails = self.queryset
        mail_count = len(mails)
        if not mails:
            messages.error(
                request,
                _(
                    "This mail either does not exist or cannot be discarded because it was sent already."
                ),
            )
            return redirect(self.request.event.orga_urls.outbox)
        for mail in mails:
            mail.log_action("pretalx.mail.delete", person=self.request.user, orga=True)
            mail.delete()

        messages.success(
            request,
            str(
                ngettext_lazy(
                    "The mail has been discarded.",
                    "{count} mails have been discarded.",
                    mail_count,
                )
            ).format(count=mail_count),
        )

        return redirect(request.event.orga_urls.outbox)


class OutboxPurge(ActionConfirmMixin, OutboxList):
    permission_required = "orga.purge_mails"
    action_object_name = ""

    @context
    def question(self):
        return _("Do you really want to purge {count} mails?").format(
            count=self.queryset.count()
        )

    def action_text(self):
        return self.question()

    @property
    def action_back_url(self):
        return self.request.event.orga_urls.outbox

    @cached_property
    def queryset(self):
        return self.get_queryset()

    def post(self, request, *args, **kwargs):
        qs = self.queryset
        count = qs.count()
        qs.delete()
        messages.success(
            request, _("{count} mails have been purged.").format(count=count)
        )
        return redirect(self.request.event.orga_urls.outbox)


class MailDetail(PermissionRequired, ActionFromUrl, CreateOrUpdateView):
    model = QueuedMail
    form_class = MailDetailForm
    template_name = "orga/mails/outbox_form.html"
    write_permission_required = "orga.edit_mails"
    permission_required = "orga.view_mails"

    def get_object(self, queryset=None) -> QueuedMail:
        return self.request.event.queued_mails.filter(pk=self.kwargs.get("pk")).first()

    def get_success_url(self):
        return self.object.event.orga_urls.outbox

    def form_valid(self, form):
        form.instance.event = self.request.event
        result = super().form_valid(form)
        if form.has_changed():
            action = "pretalx.mail." + ("update" if self.object else "create")
            form.instance.log_action(action, person=self.request.user, orga=True)
        action = form.data.get("form", "save")
        if action == "send":
            form.instance.send()
            messages.success(self.request, _("The email has been sent."))
        else:  # action == 'save'
            messages.success(
                self.request,
                _(
                    "The email has been saved. When you send it, the updated text will be used."
                ),
            )
        return result


class MailCopy(PermissionRequired, View):
    permission_required = "orga.send_mails"

    def get_object(self) -> QueuedMail:
        return get_object_or_404(
            self.request.event.queued_mails, pk=self.kwargs.get("pk")
        )

    def dispatch(self, request, *args, **kwargs):
        mail = self.get_object()
        new_mail = mail.copy_to_draft()
        messages.success(request, _("The mail has been copied, you can edit it now."))
        return redirect(new_mail.urls.edit)


class MailPreview(PermissionRequired, View):
    permission_required = "orga.send_mails"

    def get_object(self) -> QueuedMail:
        return get_object_or_404(
            self.request.event.queued_mails, pk=self.kwargs.get("pk")
        )

    def get(self, request, *args, **kwargs):
        mail = self.get_object()
        return HttpResponse(mail.make_html())


class ComposeMailChoice(EventPermissionRequired, TemplateView):
    template_name = "orga/mails/compose_choice.html"
    permission_required = "orga.send_mails"


class ComposeMailBaseView(EventPermissionRequired, FormView):
    permission_required = "orga.send_mails"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["event"] = self.request.event
        initial = kwargs.get("initial", {})
        if "template" in self.request.GET:
            template = MailTemplate.objects.filter(
                pk=self.request.GET.get("template")
            ).first()
            if template:
                initial["subject"] = template.subject
                initial["text"] = template.text
                initial["reply_to"] = template.reply_to
                initial["bcc"] = template.bcc
        for key in self.form_class.base_fields.keys():
            if key in self.request.GET:
                initial[key] = self.request.GET.get(key)
        kwargs["initial"] = initial
        return kwargs

    def get_success_url(self):
        return getattr(self, "success_url", self.request.event.orga_urls.outbox)

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx["output"] = getattr(self, "output", None)
        ctx["mail_count"] = getattr(self, "mail_count", None) or 0
        return ctx

    def form_valid(self, form):
        preview = self.request.POST.get("action") == "preview"
        if preview:
            self.output = {}
            # Only approximate, good enough. Doesn't run deduplication, so it doesn't have to
            # run rendering for all placeholders for all people, either.
            result = form.get_recipients()
            if not result:
                messages.error(
                    self.request,
                    _("There are no recipients matching this selection."),
                )
                return self.get(self.request, *self.args, **self.kwargs)
            from pretalx.common.templatetags.rich_text import rich_text

            for locale in self.request.event.locales:
                with language(locale):
                    context_dict = TolerantDict()
                    for key, value in form.get_valid_placeholders().items():
                        context_dict[key] = (
                            '<span class="placeholder" title="{title}">{content}</span>'.format(
                                title=_(
                                    "This value will be replaced based on dynamic parameters."
                                ),
                                content=escape(value.render_sample(self.request.event)),
                            )
                        )

                    subject = bleach.clean(
                        form.cleaned_data["subject"].localize(locale), tags={}
                    )
                    preview_subject = get_prefixed_subject(
                        self.request.event, subject.format_map(context_dict)
                    )
                    message = form.cleaned_data["text"].localize(locale)
                    preview_text = rich_text(message.format_map(context_dict))
                    self.output[locale] = {
                        "subject": _("Subject: {subject}").format(
                            subject=preview_subject
                        ),
                        "html": preview_text,
                    }
                    # Very rough method to deduplicate recipients, but good enough for a preview
                    self.mail_count = len({str(res) for res in result})
            return self.get(self.request, *self.args, **self.kwargs)

        result = form.save()
        if len(result) and result[0].sent:
            self.success_url = self.request.event.orga_urls.sent_mails
            messages.success(
                self.request,
                _("{count} emails have been sent.").format(count=len(result)),
            )
        else:
            self.success_url = self.request.event.orga_urls.outbox
            messages.success(
                self.request,
                phrases.orga.mails_in_outbox.format(count=len(result)),
            )
        return super().form_valid(form)


class ComposeTeamsMail(ComposeMailBaseView):
    form_class = WriteTeamsMailForm
    template_name = "orga/mails/compose_reviewer_mail_form.html"
    permission_required = "orga.send_reviewer_mails"

    def get_success_url(self):
        return self.request.event.orga_urls.outbox


class ComposeSessionMail(ComposeMailBaseView):
    form_class = WriteSessionMailForm
    template_name = "orga/mails/compose_session_mail_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        initial = kwargs.get("initial", {})
        if "submissions" in self.request.GET:
            initial["submissions"] = list(
                self.request.event.submissions.filter(
                    code__in=self.request.GET.get("submissions").split(",")
                ).values_list("code", flat=True)
            )
        if "speakers" in self.request.GET:
            initial["speakers"] = self.request.event.submitters.filter(
                code__in=self.request.GET.get("speakers").split(",")
            )
        kwargs["initial"] = initial
        return kwargs


class ComposeDraftReminders(EventPermissionRequired, FormView):
    form_class = DraftRemindersForm
    template_name = "orga/mails/send_draft_reminders.html"
    permission_required = "orga.send_mails"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["event"] = self.request.event
        return kwargs

    def get_success_url(self):
        return self.request.event.orga_urls.base

    def form_valid(self, form):
        result = form.save()
        messages.success(
            self.request,
            _("{count} emails have been sent.").format(count=result),
        )
        return super().form_valid(form)


class TemplateList(EventPermissionRequired, TemplateView):
    template_name = "orga/mails/template_list.html"
    permission_required = "orga.view_mail_templates"

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        result["templates"] = [
            {
                "title": _("Acknowledge Mail"),
                "obj": self.request.event.ack_template,
                "form": MailTemplateForm(
                    instance=self.request.event.ack_template,
                    read_only=True,
                    event=self.request.event,
                ),
            },
            {
                "title": _("Accept Mail"),
                "obj": self.request.event.accept_template,
                "form": MailTemplateForm(
                    instance=self.request.event.accept_template,
                    read_only=True,
                    event=self.request.event,
                ),
            },
            {
                "title": _("Reject Mail"),
                "obj": self.request.event.reject_template,
                "form": MailTemplateForm(
                    instance=self.request.event.reject_template,
                    read_only=True,
                    event=self.request.event,
                ),
            },
            {
                "title": _("New schedule version"),
                "obj": self.request.event.update_template,
                "form": MailTemplateForm(
                    instance=self.request.event.update_template,
                    read_only=True,
                    event=self.request.event,
                ),
            },
            {
                "title": _("Unanswered questions reminder"),
                "obj": self.request.event.question_template,
                "form": MailTemplateForm(
                    instance=self.request.event.question_template,
                    read_only=True,
                    event=self.request.event,
                ),
            },
        ]
        pks = [
            template.pk if template else None
            for template in self.request.event.fixed_templates
        ]
        result["templates"] += [
            {
                "title": str(template.subject),
                "obj": template,
                "form": MailTemplateForm(
                    instance=template, read_only=True, event=self.request.event
                ),
                "custom": True,
            }
            for template in self.request.event.mail_templates.exclude(
                pk__in=pks
            ).exclude(is_auto_created=True)
        ]
        return result


class TemplateDetail(PermissionRequired, ActionFromUrl, CreateOrUpdateView):
    model = MailTemplate
    form_class = MailTemplateForm
    template_name = "orga/mails/template_form.html"
    permission_required = "orga.view_mail_templates"
    write_permission_required = "orga.edit_mail_templates"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["event"] = self.request.event
        return kwargs

    def get_object(self) -> MailTemplate:
        return MailTemplate.objects.filter(
            event=self.request.event, pk=self.kwargs.get("pk"), is_auto_created=False
        ).first()

    @cached_property
    def object(self):
        return self.get_object()

    @cached_property
    def permission_object(self):
        return self.object or self.request.event

    def get_permission_object(self):
        return self.permission_object

    def get_success_url(self):
        return self.request.event.orga_urls.mail_templates

    def form_valid(self, form):
        form.instance.event = self.request.event
        if form.has_changed():
            action = "pretalx.mail_template." + ("update" if self.object else "create")
            form.instance.log_action(action, person=self.request.user, orga=True)
        messages.success(
            self.request,
            "The template has been saved - note that already pending emails that are based on this template will not be changed!",
        )
        return super().form_valid(form)


class TemplateDelete(PermissionRequired, View):
    permission_required = "orga.edit_mail_templates"

    def get_object(self) -> MailTemplate:
        return get_object_or_404(
            MailTemplate.objects.all(),
            event=self.request.event,
            pk=self.kwargs.get("pk"),
        )

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        template = self.get_object()
        template.log_action(
            "pretalx.mail_template.delete", person=self.request.user, orga=True
        )
        template.delete()
        messages.success(request, "The template has been deleted.")
        return redirect(request.event.orga_urls.mail_templates)
