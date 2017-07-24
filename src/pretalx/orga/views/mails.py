from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.views.generic import FormView, ListView, TemplateView, View

from pretalx.common.views import ActionFromUrl, CreateOrUpdateView
from pretalx.mail.context import get_context_explanation
from pretalx.mail.models import MailTemplate, QueuedMail
from pretalx.orga.forms.mails import (
    MailTemplateForm, OutboxMailForm, WriteMailForm,
)


class OutboxList(ListView):
    context_object_name = 'mails'
    template_name = 'orga/mails/outbox_list.html'

    def get_queryset(self):
        return self.request.event.queued_mails.all()


class OutboxSend(View):
    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        if 'pk' in self.kwargs:
            mail = self.request.event.queued_mails.get(pk=self.kwargs.get('pk'))
            mail.log_action('pretalx.mail.sent', person=self.request.user, orga=True)
            mail.send()
        else:
            for mail in self.request.event.queued_mails.all():
                mail.log_action('pretalx.mail.sent', person=self.request.user, orga=True)
                mail.send()
        return redirect(reverse('orga:mails.outbox.list', kwargs={'event': self.request.event.slug}))


class OutboxPurge(View):
    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        if 'pk' in self.kwargs:
            mail = self.request.event.queued_mails.get(pk=self.kwargs.get('pk'))
            mail.log_action('pretalx.mail.delete', person=self.request.user, orga=True)
            mail.delete()
        else:
            self.request.event.queued_mails.all().delete()
            self.request.event.log_action('pretalx.mail.delete_all')
        return redirect(reverse('orga:mails.outbox.list', kwargs={'event': self.request.event.slug}))


class OutboxMail(ActionFromUrl, CreateOrUpdateView):
    model = MailTemplate
    form_class = OutboxMailForm
    template_name = 'orga/mails/outbox_form.html'

    def get_object(self) -> MailTemplate:
        return self.request.event.queued_mails.get(pk=self.kwargs.get('pk'))

    def get_success_url(self):
        return reverse('orga:mails.outbox.list', kwargs={'event': self.object.event.slug})

    def form_valid(self, form):
        messages.success(self.request, 'The email has been saved. When you send it, the updated text will be used.')
        form.instance.event = self.request.event
        if form.has_changed():
            action = 'pretalx.mail.' + ('update' if self.object else 'create')
            form.instance.log_action(action, person=self.request.user, orga=True)
        return super().form_valid(form)


class SendMail(FormView):
    form_class = WriteMailForm
    template_name = 'orga/mails/send_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        return kwargs

    def get_success_url(self):
        return reverse('orga:mails.send', kwargs={'event': self.request.event.slug})

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

    def get_context_data(self):
        ctx = super().get_context_data()
        ctx['placeholders'] = get_context_explanation()
        return ctx

    def get_object(self) -> MailTemplate:
        return MailTemplate.objects.filter(event=self.request.event).get(pk=self.kwargs.get('pk'))

    def get_success_url(self):
        return reverse('orga:mails.templates.list', kwargs={'event': self.object.event.slug})

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
        return redirect(reverse('orga:mails.templates.list', kwargs={'event': request.event.slug}))
