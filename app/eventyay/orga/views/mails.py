import json

import nh3
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.functional import cached_property
from django.utils.html import escape
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext_lazy, npgettext_lazy
from django.views.generic import FormView, ListView, TemplateView, View
from django_context_decorator import context

from eventyay.base.models.mail import MailTemplate, QueuedMail, get_prefixed_subject

from eventyay.common.exceptions import SendMailException
from eventyay.common.language import language
from eventyay.common.mail import TolerantDict, mail_send_task
from eventyay.common.tasks import send_scheduled_queuedmail
from eventyay.common.text.phrases import phrases
from eventyay.common.views.generic import CreateOrUpdateView, OrgaCRUDView
from eventyay.common.views.mixins import (
    ActionConfirmMixin,
    ActionFromUrl,
    EventPermissionRequired,
    Filterable,
    PaginationMixin,
    PermissionRequired,
    Sortable,
)
from eventyay.helpers.timezone import format_scheduled_datetime

from eventyay.mail.signals import request_pre_send
from eventyay.orga.forms.mails import (
    DraftRemindersForm,
    MailDetailForm,
    MailTemplateForm,
    QueuedMailFilterForm,
    SessionMailRecipientsForm,
    WriteSessionMailForm,
    WriteTeamsMailForm,
)


def get_send_mail_exceptions(request):
    exceptions = [
        result[1]
        for result in request_pre_send.send_robust(sender=request.event, request=request)
        if len(result) == 2 and isinstance(result[1], SendMailException)
    ]
    if exceptions:
        errors = [str(e) for e in exceptions]
        errors = errors or [_('You cannot send emails at this time.')]
        return errors


class OutboxList(EventPermissionRequired, Sortable, Filterable, PaginationMixin, ListView):
    model = QueuedMail
    context_object_name = 'mails'
    template_name = 'orga/mails/outbox_list.html'
    default_sort_field = '-pk'
    default_filters = (
        'to__icontains',
        'subject__icontains',
        'to_users__fullname__icontains',
        'to_users__email__icontains',
    )
    sortable_fields = ('to', 'subject', 'pk')
    paginate_by = 25
    permission_required = 'base.list_queuedmail'
    lists_drafts = False

    def get_base_queryset(self):
        return (
            self.request.event.queued_mails.prefetch_related('to_users', 'submissions', 'submissions__track')
            .filter(sent__isnull=True, is_draft=self.lists_drafts)
            .order_by('-id')
        )

    def get_queryset(self):
        return self.sort_queryset(self.filter_queryset(self.get_base_queryset()))

    @context
    @cached_property
    def show_tracks(self):
        return self.request.event.get_feature_flag('use_tracks')

    @context
    @cached_property
    def is_filtered(self):
        return self.get_queryset().count() != self.get_base_queryset().count()

    def get_filter_form(self):
        return QueuedMailFilterForm(self.request.GET, event=self.request.event, sent=False)


class SentMail(EventPermissionRequired, Sortable, Filterable, PaginationMixin, ListView):
    model = QueuedMail
    context_object_name = 'mails'
    template_name = 'orga/mails/sent_list.html'
    default_filters = (
        'to__icontains',
        'subject__icontains',
        'to_users__fullname__icontains',
        'to_users__email__icontains',
    )
    default_sort_field = '-sent'
    sortable_fields = ('to', 'subject', 'sent')
    paginate_by = 25
    permission_required = 'base.list_queuedmail'

    def get_filter_form(self):
        return QueuedMailFilterForm(self.request.GET, event=self.request.event, sent=True)

    def get_queryset(self):
        qs = (
            self.request.event.queued_mails.prefetch_related('to_users', 'submissions', 'submissions__track')
            .filter(sent__isnull=False)
            .order_by('-sent')
        )
        qs = self.filter_queryset(qs)
        return self.sort_queryset(qs)

    @context
    @cached_property
    def show_tracks(self):
        return self.request.event.get_feature_flag('use_tracks')


class DraftList(OutboxList):
    """Saved but unfinished emails, kept out of the outbox so they cannot be sent."""

    template_name = 'orga/mails/draft_list.html'
    lists_drafts = True


class OutboxSend(ActionConfirmMixin, OutboxList):
    permission_required = 'base.send_queuedmail'
    action_object_name = ''
    action_confirm_label = phrases.base.send
    action_confirm_color = 'success'
    action_confirm_icon = 'envelope'

    @context
    def question(self):
        return _('Do you really want to send {count} mails?').format(count=self.queryset.count())

    def action_title(self):
        return _('Send emails')

    def action_text(self):
        return self.question()

    @property
    def action_back_url(self):
        return self.request.event.orga_urls.outbox

    def dispatch(self, request, *args, **kwargs):
        if 'pk' in self.kwargs:
            try:
                mail = self.request.event.queued_mails.get(pk=self.kwargs.get('pk'))
            except QueuedMail.DoesNotExist:
                messages.error(
                    request,
                    _('This mail either does not exist or cannot be sent because it was sent already.'),
                )
                return redirect(self.request.event.orga_urls.outbox)
            if mail.sent:
                messages.error(request, _('This mail had been sent already.'))
            else:
                errors = get_send_mail_exceptions(request)
                if errors:
                    for error in errors:
                        messages.error(request, error)
                    return redirect(self.request.event.orga_urls.outbox)
                try:
                    mail.send(requestor=self.request.user)
                    messages.success(request, _('The mail has been sent.'))
                except SendMailException as e:
                    messages.error(request, str(e))
            return redirect(self.request.event.orga_urls.outbox)
        return super().dispatch(request, *args, **kwargs)

    @cached_property
    def queryset(self):
        pks = self.request.GET.get('pks') or ''
        if pks:
            return self.request.event.queued_mails.filter(sent__isnull=True, is_draft=False, pk__in=pks.split(','))
        return self.get_queryset()

    def post(self, request, *args, **kwargs):
        mails = self.queryset
        errors = get_send_mail_exceptions(request)
        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect(self.request.event.orga_urls.outbox)
        sent_count = 0
        for mail in mails:
            try:
                mail.send(requestor=self.request.user)
                sent_count += 1
            except SendMailException as e:
                messages.error(request, str(e))
        if sent_count:
            messages.success(request, _('{count} mails have been sent.').format(count=sent_count))
        return redirect(self.request.event.orga_urls.outbox)


class DraftToOutbox(PermissionRequired, ActionConfirmMixin, TemplateView):
    """Moves a finished draft into the outbox so it can be sent."""

    permission_required = 'base.send_queuedmail'
    action_object_name = ''

    def get_permission_object(self):
        return self.request.event

    @cached_property
    def object(self):
        return get_object_or_404(
            self.request.event.queued_mails, pk=self.kwargs.get('pk'), sent__isnull=True, is_draft=True
        )

    def action_text(self):
        return self.question()

    @property
    def action_back_url(self):
        return self.request.event.orga_urls.drafts

    @context
    def question(self):
        return str(_('Move this draft to the outbox so it can be sent?'))

    def post(self, request, *args, **kwargs):
        mail = self.object
        mail.is_draft = False
        mail.save(update_fields=['is_draft'])
        messages.success(request, _('The draft has been moved to the outbox.'))
        return redirect(self.request.event.orga_urls.outbox)


class MailDelete(PermissionRequired, ActionConfirmMixin, TemplateView):
    permission_required = 'base.delete_queuedmail'
    action_object_name = ''

    def get_permission_object(self):
        return self.request.event

    @cached_property
    def queryset(self):
        mail = self.request.event.queued_mails.filter(sent__isnull=True, pk=self.kwargs.get('pk'))
        if 'all' in self.request.GET and mail:
            return self.request.event.queued_mails.filter(sent__isnull=True, template=mail.first().template)
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
            npgettext_lazy(
                'queued mail',
                'Do you really want to delete this mail?',
                'Do you really want to purge {count} mails?',
                count,
            )
        ).format(count=count)

    def post(self, request, *args, **kwargs):
        mails = self.queryset
        mail_count = len(mails)
        if not mails:
            messages.error(
                request,
                _('This mail either does not exist or cannot be discarded because it was sent already.'),
            )
            return redirect(self.request.event.orga_urls.outbox)
        for mail in mails:
            mail.log_action('eventyay.mail.delete', person=self.request.user, orga=True)
            mail.delete()

        messages.success(
            request,
            str(
                ngettext_lazy(
                    'The mail has been discarded.',
                    '{count} mails have been discarded.',
                    mail_count,
                )
            ).format(count=mail_count),
        )

        return redirect(request.event.orga_urls.outbox)


class OutboxPurge(ActionConfirmMixin, OutboxList):
    permission_required = 'base.delete_queuedmail'
    action_object_name = ''

    @context
    def question(self):
        return _('Do you really want to purge {count} mails?').format(count=self.queryset.count())

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
        messages.success(request, _('{count} mails have been purged.').format(count=count))
        return redirect(self.request.event.orga_urls.outbox)


class MailDetail(PermissionRequired, ActionFromUrl, CreateOrUpdateView):
    model = QueuedMail
    form_class = MailDetailForm
    template_name = 'orga/mails/outbox_form.html'
    write_permission_required = 'base.update_queuedmail'
    permission_required = 'base.view_queuedmail'

    def get_object(self, queryset=None) -> QueuedMail:
        return self.request.event.queued_mails.filter(pk=self.kwargs.get('pk')).first()

    def get_success_url(self):
        return self.object.event.orga_urls.outbox

    def form_valid(self, form):
        form.instance.event = self.request.event
        result = super().form_valid(form)
        if form.has_changed():
            action = 'eventyay.mail.' + ('update' if self.object else 'create')
            form.instance.log_action(action, person=self.request.user, orga=True)
        action = form.data.get('form', 'save')
        if action == 'send':
            errors = get_send_mail_exceptions(self.request)
            if errors:
                for error in errors:
                    messages.error(self.request, error)
                return redirect(self.get_success_url())
            try:
                form.instance.send(requestor=self.request.user)
                messages.success(self.request, _('The email has been sent.'))
            except SendMailException as e:
                messages.error(self.request, str(e))
        else:  # action == 'save'
            messages.success(
                self.request,
                _('The email has been saved. When you send it, the updated text will be used.'),
            )
        return result


class MailCopy(PermissionRequired, View):
    permission_required = 'base.send_queuedmail'

    def get_object(self) -> QueuedMail:
        return get_object_or_404(self.request.event.queued_mails, pk=self.kwargs.get('pk'))

    def dispatch(self, request, *args, **kwargs):
        mail = self.get_object()
        new_mail = mail.copy_to_draft()
        messages.success(request, _('The mail has been copied, you can edit it now.'))
        return redirect(new_mail.urls.edit)


class MailPreview(PermissionRequired, View):
    permission_required = 'base.send_queuedmail'

    def get_object(self) -> QueuedMail:
        return get_object_or_404(self.request.event.queued_mails, pk=self.kwargs.get('pk'))

    def get(self, request, *args, **kwargs):
        mail = self.get_object()
        return HttpResponse(mail.make_html())


class ComposeMailPreview(EventPermissionRequired, View):
    """Provides a live preview endpoint for the Tiptap email editor."""

    permission_required = 'base.send_queuedmail'

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'error': 'Invalid JSON body'}, status=400)

        html_body = data.get('html', '')
        if not isinstance(html_body, str):
            return JsonResponse({'error': 'html must be a string'}, status=400)

        locale = data.get('locale') or request.event.locale

        from eventyay.common.sanitizers import sanitize_email_html
        from eventyay.base.templatetags.rich_text import build_email_preview_context
        from eventyay.base.services.mail import expand_email_variable_chips

        safe_html = sanitize_email_html(html_body)

        with language(locale):
            context_dict = build_email_preview_context(
                request.event,
                ['event', 'submission', 'user', 'slot'],
            )
            expanded = safe_html.format_map(context_dict)
            preview_html = expand_email_variable_chips(expanded, dict(context_dict))
            return JsonResponse({'html': preview_html})


class ComposeMailChoice(EventPermissionRequired, TemplateView):
    template_name = 'orga/mails/compose_choice.html'
    permission_required = 'base.send_queuedmail'


class ComposeMailBaseView(EventPermissionRequired, FormView):
    permission_required = 'base.send_queuedmail'
    # Composers whose emails always go out directly cannot hold a draft.
    supports_drafts = True

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        kwargs['user'] = self.request.user
        initial = kwargs.get('initial', {})
        if 'template' in self.request.GET:
            template = self.request.event.mail_templates.filter(pk=self.request.GET.get('template')).first()
            if template:
                kwargs['source_template'] = template
                initial['subject'] = template.subject
                initial['text'] = template.text
                initial['reply_to'] = template.reply_to
                initial['bcc'] = template.bcc
        for key in self.form_class.base_fields.keys():
            if key in self.request.GET:
                initial[key] = self.request.GET.get(key)
        kwargs['initial'] = initial

        errors = get_send_mail_exceptions(self.request)
        kwargs['may_skip_queue'] = not bool(errors)
        return kwargs

    def get_success_url(self):
        return getattr(self, 'success_url', self.request.event.orga_urls.outbox)

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['output'] = getattr(self, 'output', None)
        ctx['mail_count'] = getattr(self, 'mail_count', None) or 0
        return ctx

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if request.POST.get('action') == 'test':
            for field_name in list(form.fields.keys()):
                if field_name == 'subject' or field_name.startswith('subject_'):
                    form.fields[field_name].required = False
                    if hasattr(form.fields[field_name], 'one_required'):
                        form.fields[field_name].one_required = False
                if field_name == 'text' or field_name.startswith('text_'):
                    form.fields[field_name].required = False
                    if hasattr(form.fields[field_name], 'one_required'):
                        form.fields[field_name].one_required = False
        if form.is_valid():
            return self.form_valid(form)
        return self.form_invalid(form)

    def send_test_email(self, form):
        address = form.cleaned_data.get('test_email')
        if not address:
            form.add_error(
                'test_email',
                _('Please enter an email address to send the test email to.')
            )
            return self.render_to_response(self.get_context_data(form=form))

        from eventyay.base.templatetags.rich_text import compile_email_body

        event = self.request.event
        locale = event.locale
        with language(locale):
            context_dict = TolerantDict()
            for key, value in form.get_valid_placeholders().items():
                context_dict[key] = value.render_sample(event)
                
            subject_data = form.cleaned_data.get('subject')
            subject = nh3.clean(subject_data.localize(locale), tags=set()) if subject_data else ""
            if not subject.strip():
                subject = str(_("Example Subject for {event_name}"))
            subject = get_prefixed_subject(event, subject.format_map(context_dict))
            
            text_data = form.cleaned_data.get('text')
            text = text_data.localize(locale) if text_data else ""
            if not text.strip():
                if 'proposal_title' in context_dict:
                    text = str(_("Hello {name},\n\nThis is an example test email for your proposal \"{proposal_title}\" at {event_name}.\n\nBest regards,\nThe {event_name} team"))
                else:
                    text = str(_("Hello {name},\n\nThis is an example test email for {event_name}.\n\nBest regards,\nThe {event_name} team"))
            text = text.format_map(context_dict)

        mail_send_task.apply_async(
            kwargs={
                'to': [address],
                'subject': subject,
                'body': text,
                'html': compile_email_body(text),
                'reply_to': form.cleaned_data.get('reply_to') or '',
                'event': event.pk,
            }
        )
        messages.success(
            self.request,
            _('A test email has been sent to {address}.').format(address=address),
        )
        return self.render_to_response(self.get_context_data(form=form))

    def form_valid(self, form):
        action = self.request.POST.get('action')
        if action == 'test':
            return self.send_test_email(form)
        is_draft = action == 'draft'
        if is_draft and not self.supports_drafts:
            messages.error(
                self.request,
                _('This kind of email cannot be saved as a draft.'),
            )
            return self.render_to_response(self.get_context_data(form=form))
        if is_draft:
            # Drafts are kept out of the outbox and are never dispatched, so
            # neither an immediate send nor a send time may survive the save.
            form.cleaned_data['skip_queue'] = False
            form.cleaned_data['scheduled_at'] = None
        preview = action == 'preview'
        if preview:
            self.output = {}
            # Only approximate, good enough. Doesn't run deduplication, so it doesn't have to
            # run rendering for all placeholders for all people, either.
            result = form.get_recipients()
            
            from eventyay.base.templatetags.rich_text import compile_email_body


            # Very rough method to deduplicate recipients, but good enough for a preview
            self.mail_count = len({str(res) for res in result}) if result else 0
            if not result:
                messages.warning(
                    self.request,
                    _('Preview generated with sample recipient data because no recipient is currently selected.')
                )

            for locale in self.request.event.locales:
                with language(locale):
                    context_dict = TolerantDict()
                    for key, value in form.get_valid_placeholders().items():
                        context_dict[key] = '<span class="placeholder" title="{title}">{content}</span>'.format(
                            title=_('This value will be replaced based on dynamic parameters.'),
                            content=escape(value.render_sample(self.request.event)),
                        )

                    subject = nh3.clean(form.cleaned_data['subject'].localize(locale), tags=set())
                    preview_subject = get_prefixed_subject(self.request.event, subject.format_map(context_dict))
                    message = form.cleaned_data['text'].localize(locale)
                    preview_text = compile_email_body(message.format_map(context_dict))
                    self.output[locale] = {
                        'subject': _('Subject: {subject}').format(subject=preview_subject),
                        'html': preview_text,
                    }
            return self.get(self.request, *self.args, **self.kwargs)

        with transaction.atomic():
            result = form.save()
            if is_draft and result:
                # Until this runs, the rows look like ordinary outbox entries.
                QueuedMail.objects.filter(pk__in=[mail.pk for mail in result]).update(is_draft=True)
        scheduled_at = form.cleaned_data.get('scheduled_at')
        if len(result) and result[0].sent:
            self.success_url = self.request.event.orga_urls.sent_mails
            messages.success(
                self.request,
                _('{count} emails have been sent.').format(count=len(result)),
            )
        elif scheduled_at:
            if not result:
                messages.error(self.request, _('No emails could be created. Please check your recipient selection.'))
                return redirect(self.request.event.orga_urls.compose_mails_sessions)
            self.success_url = self.request.event.orga_urls.outbox
            for mail in result:
                mail.log_action(
                    'eventyay.mail.scheduled',
                    person=self.request.user,
                    orga=True,
                    data={'scheduled_at': scheduled_at.isoformat()},
                )
            for mail in result:
                send_scheduled_queuedmail.apply_async(args=[mail.pk], eta=scheduled_at)
            messages.success(
                self.request,
                _('{count} emails have been scheduled for {datetime} ({timezone}).').format(
                    count=len(result),
                    datetime=format_scheduled_datetime(self.request.event, scheduled_at),
                    timezone=self.request.event.timezone,
                ),
            )
        elif is_draft:
            self.success_url = self.request.event.orga_urls.drafts
            messages.success(
                self.request,
                _('{count} emails have been saved as drafts.').format(count=len(result)),
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
    template_name = 'orga/mails/compose_reviewer_mail_form.html'
    permission_required = 'base.update_team'
    # WriteTeamsMailForm.save() sends every mail as it builds it and never
    # commits it, so there is no row left to mark as a draft.
    supports_drafts = False

    def dispatch(self, request, *args, **kwargs):
        # Gotta handle errors directly here, as these emails are always sent directly
        errors = get_send_mail_exceptions(request)
        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect(self.request.event.orga_urls.outbox)
        return super().dispatch(request, *args, **kwargs)


class ComposeSessionMail(ComposeMailBaseView):
    form_class = WriteSessionMailForm
    template_name = 'orga/mails/compose_session_mail_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        initial = kwargs.get('initial', {})
        if 'submissions' in self.request.GET:
            initial['submissions'] = list(
                self.request.event.submissions.filter(
                    code__in=self.request.GET.get('submissions').split(',')
                ).values_list('code', flat=True)
            )
        if 'speakers' in self.request.GET:
            initial['speakers'] = self.request.event.submitters.filter(
                code__in=self.request.GET.get('speakers').split(',')
            )
        kwargs['initial'] = initial
        return kwargs


class ComposeSessionMailRecipients(EventPermissionRequired, View):
    """Returns the audience matching the filters in the query string."""

    permission_required = 'base.send_queuedmail'

    # WriteSessionMailForm reads these filters from initial rather than from the
    # submitted data, so the preview has to pass them the same way the composer does.
    initial_filter_keys = ('q', 'question', 'answer', 'answer__options', 'unanswered')

    def get(self, request, *args, **kwargs):
        initial = {key: request.GET[key] for key in self.initial_filter_keys if key in request.GET}
        form = SessionMailRecipientsForm(event=request.event, data=request.GET, initial=initial)
        if not form.is_valid():
            return JsonResponse({'error': form.errors}, status=400)

        recipients = {}
        for entry in form.get_recipients():
            user = entry['user']
            recipient = recipients.setdefault(
                user.pk,
                {
                    'name': user.get_display_name(),
                    'email': user.email or '',
                    'submissions': [],
                    'directly_selected': False,
                },
            )
            submission = entry.get('submission')
            if submission:
                recipient['submissions'].append(
                    {
                        'title': str(submission.title),
                        'state': submission.get_state_display(),
                    }
                )
            else:
                recipient['directly_selected'] = True

        return JsonResponse(
            {
                'count': len(recipients),
                'recipients': sorted(recipients.values(), key=lambda r: r['email']),
            }
        )


class ComposeDraftReminders(EventPermissionRequired, FormView):
    form_class = DraftRemindersForm
    template_name = 'orga/mails/send_draft_reminders.html'
    permission_required = 'base.send_queuedmail'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        return kwargs

    def get_success_url(self):
        return self.request.event.orga_urls.base

    def form_valid(self, form):
        result = form.save()
        messages.success(
            self.request,
            _('{count} emails have been sent.').format(count=result),
        )
        return super().form_valid(form)


class MailTemplateView(OrgaCRUDView):
    model = MailTemplate
    form_class = MailTemplateForm
    template_namespace = 'orga/mails'
    messages = {
        'create': phrases.base.saved,
        'update': _(
            'The template has been saved - note that already pending emails that are based on this '
            'template will not be changed!'
        ),
        'delete': phrases.base.deleted,
    }

    def get_queryset(self):
        qs = self.request.event.mail_templates.filter(is_auto_created=False).order_by('role')
        for template in qs:
            if template.role:
                self.request.event._ensure_mail_template_locales(template, template.role)
        return qs

    def get_generic_title(self, instance=None):
        if instance:
            if not instance.role:
                return _('Email template') + f': {instance.subject}'
            else:
                return _('Email template') + f': {instance.get_role_display()}'
        if self.action == 'create':
            return _('New email template')
        return _('Email templates')
