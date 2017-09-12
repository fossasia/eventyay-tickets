from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import ugettext_lazy as _
from django.views.generic import FormView, ListView, TemplateView, View

from pretalx.common.views import (
    ActionFromUrl, CreateOrUpdateView, Filterable, Sortable,
)
from pretalx.mail.context import get_context_explanation
from pretalx.mail.models import MailTemplate, QueuedMail
from pretalx.orga.forms.mails import (
    MailDetailForm, MailTemplateForm, WriteMailForm,
)


class OutboxList(Sortable, Filterable, ListView):
    context_object_name = 'mails'
    template_name = 'orga/mails/outbox_list.html'
    default_filters = ('to__icontains', 'subject__icontains')
    filterable_fields = ('to', 'subject', )
    sortable_fields = ('to', 'subject', )

    def get_queryset(self):
        qs = self.request.event.queued_mails.filter(sent__isnull=True)
        qs = self.filter_queryset(qs)
        qs = self.sort_queryset(qs)
        return qs


class SentMail(Sortable, Filterable, ListView):
    context_object_name = 'mails'
    template_name = 'orga/mails/sent_list.html'
    default_filters = ('to__icontains', 'subject__icontains')
    filterable_fields = ('to', 'subject', )
    sortable_fields = ('to', 'subject', 'sent', )

    def get_queryset(self):
        qs = self.request.event.queued_mails.filter(sent__isnull=False).order_by('-sent')
        qs = self.filter_queryset(qs)
        qs = self.sort_queryset(qs)
        return qs


class OutboxSend(View):

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        if 'pk' in self.kwargs:
            try:
                mail = self.request.event.queued_mails.get(pk=self.kwargs.get('pk'))
            except QueuedMail.DoesNotExist:
                messages.error(request, _('This mail either does not exist or cannot be discarded because it was sent already.'))
                return redirect(self.request.event.orga_urls.outbox)
            if mail.sent:
                messages.error(request, _('This mail had been sent already.'))
            else:
                mail.send()
                mail.log_action('pretalx.mail.sent', person=self.request.user, orga=True)
                messages.success(request, _('The mail has been sent.'))
        else:
            qs = self.request.event.queued_mails.filter(sent__isnull=True)
            count = qs.count()
            for mail in self.request.event.queued_mails.filter(sent__isnull=True):
                mail.log_action('pretalx.mail.sent', person=self.request.user, orga=True)
                mail.send()
            messages.success(request, _('{count} mails have been sent.').format(count=count))
        return redirect(self.request.event.orga_urls.outbox)


class OutboxPurge(View):

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        if 'pk' in self.kwargs:
            try:
                mail = self.request.event.queued_mails.get(sent__isnull=True, pk=self.kwargs.get('pk'))
            except QueuedMail.DoesNotExist:
                messages.error(request, _('This mail either does not exist or cannot be discarded because it was sent already.'))
                return redirect(self.request.event.orga_urls.outbox)
            mail.log_action('pretalx.mail.delete', person=self.request.user, orga=True)
            mail.delete()
            messages.success(request, _('The mail has been deleted.'))
        else:
            self.request.event.log_action('pretalx.mail.delete_all')
            self.request.event.queued_mails.filter(sent__isnull=True).delete()
            messages.success(request, _('The mails have been deleted.'))
        return redirect(request.event.orga_urls.outbox)


class MailDetail(ActionFromUrl, CreateOrUpdateView):
    model = MailTemplate
    form_class = MailDetailForm
    template_name = 'orga/mails/outbox_form.html'

    def get_object(self) -> MailTemplate:
        return self.request.event.queued_mails.get(pk=self.kwargs.get('pk'))

    def get_success_url(self):
        return self.object.event.orga_urls.outbox

    def form_valid(self, form):
        if form.instance.sent:
            messages.error(self.request, _('The email has already been sent, you cannot edit it anymore.'))
            return redirect(self.get_success_url())

        ret = super().form_valid(form)
        messages.success(self.request, _('The email has been saved. When you send it, the updated text will be used.'))
        form.instance.event = self.request.event
        if form.has_changed():
            action = 'pretalx.mail.' + ('update' if self.object else 'create')
            form.instance.log_action(action, person=self.request.user, orga=True)
        return ret


class MailCopy(View):

    def dispatch(self, request, *args, **kwargs):
        mail = self.request.event.queued_mails.get(pk=self.kwargs['pk'])
        new_mail = mail.copy_to_draft()
        messages.success(request, _('The mail has been copied, you can edit it now.'))
        return redirect(new_mail.urls.edit)


class SendMail(FormView):
    form_class = WriteMailForm
    template_name = 'orga/mails/send_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        return kwargs

    def get_success_url(self):
        return self.request.event.orga_urls.send_mails

    def form_valid(self, form):
        email_set = set()

        for state in form.cleaned_data.get('recipients'):
            if state == 'selected_submissions':
                submission_filter = {'code__in': form.cleaned_data.get('submissions')}
            else:
                submission_filter = {'state': state}
            email_set.update(self.request.event.submissions.filter(**submission_filter).values_list('speakers__email', flat=True))

        for email in email_set:
            QueuedMail.objects.create(
                event=self.request.event, to=email, reply_to=form.cleaned_data.get('reply_to'),
                cc=form.cleaned_data.get('cc'), bcc=form.cleaned_data.get('bcc'),
                subject=form.cleaned_data.get('subject'), text=form.cleaned_data.get('text')
            )
        messages.success(self.request, _('The emails have been saved to the outbox – you can make individual changes there or just send them all.'))
        return super().form_valid(form)


class TemplateList(TemplateView):
    template_name = 'orga/mails/template_list.html'

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        accept = self.request.event.accept_template
        ack = self.request.event.ack_template
        reject = self.request.event.reject_template
        ctx['accept'] = MailTemplateForm(instance=accept, read_only=True)
        ctx['ack'] = MailTemplateForm(instance=ack, read_only=True)
        ctx['reject'] = MailTemplateForm(instance=reject, read_only=True)
        ctx['other'] = [
            MailTemplateForm(instance=template, read_only=True)
            for template
            in self.request.event.mail_templates.exclude(pk__in=[accept.pk, ack.pk, reject.pk])
        ]
        return ctx


class TemplateDetail(ActionFromUrl, CreateOrUpdateView):
    model = MailTemplate
    form_class = MailTemplateForm
    template_name = 'orga/mails/template_form.html'

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['placeholders'] = get_context_explanation()
        return ctx

    def get_object(self) -> MailTemplate:
        return MailTemplate.objects.filter(event=self.request.event).get(pk=self.kwargs.get('pk'))

    def get_success_url(self):
        return self.request.event.orga_urls.mail_templates

    def form_valid(self, form):
        messages.success(self.request, 'The template has been saved - note that already pending emails that are based on this template will not be changed!')
        form.instance.event = self.request.event
        if form.has_changed():
            action = 'pretalx.mail_template.' + ('update' if self.object else 'create')
            form.instance.log_action(action, person=self.request.user, orga=True)
        return super().form_valid(form)


class TemplateDelete(View):

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        template = MailTemplate.objects.filter(event=self.request.event).get(pk=self.kwargs.get('pk'))
        template.log_action('pretalx.mail_template.delete', person=self.request.user, orga=True)
        template.delete()
        messages.success(request, 'The template has been deleted.')
        return redirect(request.event.orga_urls.mail_templates)
