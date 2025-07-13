import logging

import bleach
import uuid
from django.contrib import messages
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _, ngettext_lazy
from django.views.generic import FormView, ListView, TemplateView, UpdateView, View

from pretix.base.email import get_available_placeholders
from pretix.base.i18n import language
from pretix.base.models import CachedFile, Event, LogEntry, Order, OrderPosition
from pretix.base.models.event import SubEvent
from pretix.base.services.mail import TolerantDict
from pretix.base.templatetags.rich_text import markdown_compile_email
from pretix.control.permissions import EventPermissionRequiredMixin
from pretix.plugins.sendmail.forms import QueuedMailEditForm
from pretix.plugins.sendmail.mixins import CopyDraftMixin, QueryFilterOrderingMixin
from pretix.plugins.sendmail.models import ComposingFor, QueuedMail
from pretix.plugins.sendmail.tasks import send_queued_mail
from pretix.control.views.event import EventSettingsFormView, EventSettingsViewMixin
from .forms import MailContentSettingsForm, TeamMailForm


from . import forms

logger = logging.getLogger('pretix.plugins.sendmail')


def stringify_uuids(obj):
    """
    Recursively converts UUIDs to strings inside a nested dict or list
    """
    if isinstance(obj, dict):
        return {k: stringify_uuids(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [stringify_uuids(i) for i in obj]
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    return obj

class ComposeMailChoice(EventPermissionRequiredMixin, TemplateView):
    permission_required = 'can_change_orders'
    template_name = 'pretixplugins/sendmail/compose_choice.html'


class SenderView(EventPermissionRequiredMixin, CopyDraftMixin, FormView):
    template_name = 'pretixplugins/sendmail/send_form.html'
    permission = 'can_change_orders'
    form_class = forms.MailForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        self.load_copy_draft(self.request, kwargs)
        return kwargs

    def form_invalid(self, form):
        messages.error(self.request, _('We could not queue the email. See below for details.'))
        return super().form_invalid(form)

    def form_valid(self, form):
        qs = Order.objects.filter(event=self.request.event)
        statusq = Q(status__in=form.cleaned_data['sendto'])
        if 'overdue' in form.cleaned_data['sendto']:
            statusq |= Q(status=Order.STATUS_PENDING, expires__lt=now())
        if 'pa' in form.cleaned_data['sendto']:
            statusq |= Q(status=Order.STATUS_PENDING, require_approval=True)
        if 'na' in form.cleaned_data['sendto']:
            statusq |= Q(status=Order.STATUS_PENDING, require_approval=False)
        orders = qs.filter(statusq)

        opq = OrderPosition.objects.filter(
            order=OuterRef('pk'),
            canceled=False,
            item_id__in=[i.pk for i in form.cleaned_data.get('items')],
        )

        if form.cleaned_data.get('filter_checkins'):
            ql = []
            if form.cleaned_data.get('not_checked_in'):
                ql.append(Q(checkins__list_id=None))
            if form.cleaned_data.get('checkin_lists'):
                ql.append(
                    Q(
                        checkins__list_id__in=[i.pk for i in form.cleaned_data.get('checkin_lists', [])],
                    )
                )
            if len(ql) == 2:
                opq = opq.filter(ql[0] | ql[1])
            elif ql:
                opq = opq.filter(ql[0])
            else:
                opq = opq.none()

        if form.cleaned_data.get('subevent'):
            opq = opq.filter(subevent=form.cleaned_data.get('subevent'))
        if form.cleaned_data.get('subevents_from'):
            opq = opq.filter(subevent__date_from__gte=form.cleaned_data.get('subevents_from'))
        if form.cleaned_data.get('subevents_to'):
            opq = opq.filter(subevent__date_from__lt=form.cleaned_data.get('subevents_to'))
        if form.cleaned_data.get('created_from'):
            opq = opq.filter(order__datetime__gte=form.cleaned_data.get('created_from'))
        if form.cleaned_data.get('created_to'):
            opq = opq.filter(order__datetime__lt=form.cleaned_data.get('created_to'))

        orders = orders.annotate(match_pos=Exists(opq)).filter(match_pos=True).distinct()

        self.output = {}
        if not orders:
            messages.error(self.request, _('There are no orders matching this selection.'))
            return self.get(self.request, *self.args, **self.kwargs)

        if self.request.POST.get('action') == 'preview':
            for l in self.request.event.settings.locales:
                with language(l, self.request.event.settings.region):
                    context_dict = TolerantDict()
                    for k, v in get_available_placeholders(
                        self.request.event, ['event', 'order', 'position_or_address']
                    ).items():
                        context_dict[k] = '<span class="placeholder" title="{}">{}</span>'.format(
                            _('This value will be replaced based on dynamic parameters.'),
                            v.render_sample(self.request.event),
                        )

                    subject = bleach.clean(form.cleaned_data['subject'].localize(l), tags=[])
                    preview_subject = subject.format_map(context_dict)
                    message = form.cleaned_data['message'].localize(l)
                    preview_text = markdown_compile_email(message.format_map(context_dict))

                    self.output[l] = {
                        'subject': _('Subject: {subject}').format(subject=preview_subject),
                        'html': preview_text,
                    }

            return self.get(self.request, *self.args, **self.kwargs)

        # Build filters JSON for later use in QueuedMail
        filters = {
            'recipients': form.cleaned_data['recipients'],
            'sendto': form.cleaned_data['sendto'],
            'orders': list(orders.values_list('pk', flat=True)),
            'items': [i.pk for i in form.cleaned_data.get('items')],
            'checkin_lists': [cl.pk for cl in form.cleaned_data.get('checkin_lists')],
            'filter_checkins': form.cleaned_data.get('filter_checkins'),
            'not_checked_in': form.cleaned_data.get('not_checked_in'),
            'subevent': form.cleaned_data.get('subevent').pk if form.cleaned_data.get('subevent') else None,
            'subevents_from': form.cleaned_data.get('subevents_from').isoformat() if form.cleaned_data.get('subevents_from') else None,
            'subevents_to': form.cleaned_data.get('subevents_to').isoformat() if form.cleaned_data.get('subevents_to') else None,
            'created_from': form.cleaned_data.get('created_from').isoformat() if form.cleaned_data.get('created_from') else None,
            'created_to': form.cleaned_data.get('created_to').isoformat() if form.cleaned_data.get('created_to') else None,
        }

        qm = QueuedMail.objects.create(
            event=self.request.event,
            user=self.request.user,
            raw_subject=form.cleaned_data['subject'].data,
            raw_message=form.cleaned_data['message'].data,
            filters=stringify_uuids(filters),
            attachments=[str(form.cleaned_data['attachment'].id)] if form.cleaned_data.get('attachment') else [],
            locale=self.request.event.settings.locale,
            reply_to=self.request.event.settings.get('contact_mail'),
            bcc=self.request.event.settings.get('mail_bcc'),
        )

        qm.populate_to_users()

        messages.success(
            self.request,
            _('Your email has been sent to the outbox.')
        )

        return redirect(
            'plugins:sendmail:send',
            event=self.request.event.slug,
            organizer=self.request.event.organizer.slug,
        )

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['output'] = getattr(self, 'output', None)
        return ctx


class EmailHistoryView(EventPermissionRequiredMixin, ListView):
    template_name = 'pretixplugins/sendmail/history.html'
    permission = 'can_change_orders'
    model = LogEntry
    context_object_name = 'logs'
    paginate_by = 5

    def get_queryset(self):
        qs = LogEntry.objects.filter(
            event=self.request.event, action_type='pretix.plugins.sendmail.sent'
        ).select_related('event', 'user')
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()

        itemcache = {i.pk: str(i) for i in self.request.event.items.all()}
        checkin_list_cache = {i.pk: str(i) for i in self.request.event.checkin_lists.all()}
        status = dict(Order.STATUS_CHOICE)
        status['overdue'] = _('pending with payment overdue')
        status['na'] = _('payment pending (except unapproved)')
        status['pa'] = _('approval pending')
        status['r'] = status['c']
        for log in ctx['logs']:
            log.pdata = log.parsed_data
            log.pdata['locales'] = {}
            for locale, msg in log.pdata['message'].items():
                log.pdata['locales'][locale] = {
                    'message': msg,
                    'subject': log.pdata['subject'][locale],
                }
            log.pdata['sendto'] = [status[s] for s in log.pdata['sendto']]
            log.pdata['items'] = [itemcache.get(i['id'], '?') for i in log.pdata.get('items', [])]
            log.pdata['checkin_lists'] = [
                checkin_list_cache.get(i['id'], '?')
                for i in log.pdata.get('checkin_lists', [])
                if i['id'] in checkin_list_cache
            ]
            if log.pdata.get('subevent'):
                try:
                    log.pdata['subevent_obj'] = self.request.event.subevents.get(pk=log.pdata['subevent']['id'])
                except SubEvent.DoesNotExist:
                    pass

        return ctx


class MailTemplatesView(EventSettingsViewMixin, EventSettingsFormView):
    model = Event
    template_name = 'pretixplugins/sendmail/mail_templates.html'
    form_class = MailContentSettingsForm
    permission = 'can_change_event_settings'

    def get_success_url(self) -> str:
        return reverse(
            'plugins:sendmail:templates',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )

    def form_invalid(self, form):
        messages.error(
            self.request,
            _('We could not save your changes. See below for details.'),
        )
        return super().form_invalid(form)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if not form.is_valid():
            return self.form_invalid(form)
        
        form.save()
        if form.has_changed():
            self.request.event.log_action(
                'pretix.event.settings',
                user=self.request.user,
                data={k: form.cleaned_data.get(k) for k in form.changed_data},
            )
        messages.success(self.request, _('Your changes have been saved.'))
        return redirect(self.get_success_url())


class OutboxListView(EventPermissionRequiredMixin, QueryFilterOrderingMixin, ListView):
    model = QueuedMail
    context_object_name = 'mails'
    template_name = 'pretixplugins/sendmail/outbox_list.html'
    permission_required = 'can_change_orders'
    paginate_by = 25

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['headers'] = [
            ('subject', _('Subject')),
            ('recipient', _('To')),
        ]
        ctx['current_ordering'] = self.request.GET.get('ordering')
        ctx['query'] = self.request.GET.get('q', '')

        MAX_ERRORS_TO_SHOW = 2
        for mail in ctx['mails']:
            errors = [user for user in (mail.to_users or []) if user.get('error')]
            mail.recipient_errors_preview = errors[:MAX_ERRORS_TO_SHOW]
            mail.recipient_error_count = len(errors)

        return ctx

    def get_queryset(self):
        base_qs = self.model.objects.filter(event=self.request.event, sent_at__isnull=True).select_related('event', 'user')
        return self.get_filtered_queryset(base_qs)


class SendQueuedMailView(EventPermissionRequiredMixin, View):
    permission_required = 'can_change_orders'

    def post(self, request, *args, **kwargs):
        mail = get_object_or_404(
            QueuedMail,
            event=request.event,
            pk=kwargs['pk']
        )

        if mail.sent_at:
            messages.warning(request, _('This mail has already been sent.'))
        else:
            # Enqueue the Celery task
            send_queued_mail.apply_async(args=[request.event.pk, mail.pk])
            messages.success(
                request,
                _('The mail has been queued for sending. It will be sent shortly.')
            )

        return HttpResponseRedirect(reverse('plugins:sendmail:outbox', kwargs={
            'organizer': request.event.organizer.slug,
            'event': request.event.slug,
        }))


class EditQueuedMailView(EventPermissionRequiredMixin, UpdateView):
    model = QueuedMail
    form_class = QueuedMailEditForm
    template_name = 'pretixplugins/sendmail/outbox_form.html'
    permission_required = 'can_change_orders'

    def get_object(self, queryset=None):
        return get_object_or_404(
            QueuedMail, event=self.request.event, pk=self.kwargs["pk"]
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['read_only'] = self.object.sent_at

        if self.object.attachments:
            ctx['attachments_files'] = CachedFile.objects.filter(
                id__in=[uuid.UUID(att_id) for att_id in self.object.attachments]
            )
        else:
            ctx['attachments_files'] = []
        return ctx

    def form_valid(self, form):
        if form.instance.sent_at:
            messages.error(self.request, _('This email has already been sent and cannot be edited.'))
            return self.form_invalid(form)

        response = super().form_valid(form)

        action = self.request.POST.get('action')
        if action == 'save_and_send':
            if form.instance.send(async_send=True):
                messages.success(self.request, _('Your changes have been saved and the email has been queued for sending.'))
            else:
                messages.error(self.request, _('Your changes have been saved, but sending the email failed.'))
        else:
            messages.success(self.request, _('Your changes have been saved.'))

        return response

    def get_success_url(self):
        return reverse('plugins:sendmail:outbox', kwargs={
            'organizer': self.request.event.organizer.slug,
            'event': self.request.event.slug
        })


class DeleteQueuedMailView(EventPermissionRequiredMixin, TemplateView):
    permission_required = 'can_change_orders'
    template_name = 'pretixplugins/sendmail/delete_confirmation.html'
    permission_required = 'can_change_orders'

    @cached_property
    def mail(self):
        return get_object_or_404(
            QueuedMail, event=self.request.event, pk=self.kwargs['pk']
        )

    def question(self):
        return _("Do you really want to delete this mail?")
    
    def post(self, request, *args, **kwargs):
        mail = self.mail
        if mail.sent_at:
            messages.error(
                request,
                _("This mail has already been sent and cannot be deleted.")
            )
        else:
            mail.delete()
            messages.success(
                request,
                _("The mail has been deleted.")
            )

        return redirect(reverse('plugins:sendmail:outbox', kwargs={
            'organizer': request.event.organizer.slug,
            'event': request.event.slug
        }))


class PurgeQueuedMailsView(EventPermissionRequiredMixin, TemplateView):
    permission_required = 'can_change_orders'
    template_name = 'pretixplugins/sendmail/purge_confirmation.html'

    def get_permission_object(self):
        return self.request.event
    
    def question(self):
        count = QueuedMail.objects.filter(event=self.request.event, sent_at__isnull=True).count()
        return ngettext_lazy(
            "Do you really want to purge the mail?",
            "Do you really want to purge {count} mails?",
            count
        ).format(count=count)

    def post(self, request, *args, **kwargs):
        qs = QueuedMail.objects.filter(event=request.event, sent_at__isnull=True)
        count = qs.count()
        qs.delete()

        messages.success(
            request,
            ngettext_lazy(
                "One mail has been discarded.",
                "{count} mails have been discarded.",
                count
            ).format(count=count)
        )
        return redirect(reverse('plugins:sendmail:outbox', kwargs={
            'organizer': request.event.organizer.slug,
            'event': request.event.slug
        }))


class SentMailView(EventPermissionRequiredMixin, QueryFilterOrderingMixin, ListView):
    model = QueuedMail
    context_object_name = "mails"
    template_name = "pretixplugins/sendmail/sent_list.html"
    permission_required = "can_change_orders"
    paginate_by = 25

    def get_queryset(self):
        base_qs = self.model.objects.filter(event=self.request.event, sent_at__isnull=False).select_related('event', 'user')
        return self.get_filtered_queryset(base_qs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['headers'] = [
            ('subject', _('Subject')),
            ('recipient', _('To')),
            ('created', _('Sent at')),
        ]
        ctx['current_ordering'] = self.request.GET.get('ordering')
        ctx['query'] = self.request.GET.get('q', '')
        return ctx


class ComposeTeamsMail(EventPermissionRequiredMixin, CopyDraftMixin, FormView):
    template_name = 'pretixplugins/sendmail/send_team_form.html'
    permission = 'can_change_orders'
    form_class = TeamMailForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        self.load_copy_draft(self.request, kwargs, team_mode=True)
        return kwargs
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['output'] = getattr(self, 'output', None)

        return ctx

    def form_valid(self, form):
        event = self.request.event
        user = self.request.user
        subject = form.cleaned_data['subject']
        message = form.cleaned_data['message']

        self.output = {}
        for l in event.settings.locales:
            with language(l, event.settings.region):
                context_dict = {
                    k: f"""<span class="placeholder" title="{
                        _('This value will be replaced based on dynamic parameters.')
                        }">{v.render_sample(self.request.event)}</span>"""
                    for k, v in get_available_placeholders(event, ['event', 'team']).items()
                }

                try:
                    subject_preview = subject.localize(l).format_map(context_dict)
                except KeyError as e:
                    form.add_error('subject', _('Invalid placeholder(s): {}').format(str(e)))
                    return self.form_invalid(form)

                try:
                    message_preview = message.localize(l).format_map(context_dict)
                except KeyError as e:
                    form.add_error('message', _('Invalid placeholder(s): {}').format(str(e)))
                    return self.form_invalid(form)

                if self.request.POST.get('action') == 'preview':
                    self.output[l] = {
                        'subject': _('Subject: {subject}').format(subject=subject_preview),
                        'html': markdown_compile_email(message_preview),
                    }

        if self.request.POST.get('action') == 'preview':
            return self.get(self.request, *self.args, **self.kwargs)

        sent_emails = set()
        to_users = []

        for team in form.cleaned_data['teams']:
            for member in team.members.all():
                if not member.email or member.email in sent_emails:
                    continue

                to_users.append({
                    "email": member.email,
                    "team": team.pk,
                    "orders": [],
                    "positions": [],
                    "items": [],
                    "sent": False,
                    "error": None
                })

                sent_emails.add(member.email)

        if not to_users:
            messages.error(self.request, _('There are no valid recipients for the selected teams.'))
            return self.form_invalid(form)

        QueuedMail.objects.create(
            event=event,
            user=user,
            to_users=to_users,
            composing_for=ComposingFor.TEAMS,
            raw_subject=subject.data,
            raw_message=message.data,
            locale=event.settings.locale,
            reply_to=event.settings.get('contact_mail'),
            bcc=event.settings.get('mail_bcc'),
            attachments=[str(form.cleaned_data['attachment'].id)] if form.cleaned_data.get('attachment') else [],
            filters={'teams': [team.pk for team in form.cleaned_data['teams']]},
        )

        messages.success(
            self.request,
            _('Your email has been sent to the outbox.')
        )

        return redirect(
            'plugins:sendmail:compose_email_teams',
            event=event.slug,
            organizer=event.organizer.slug
        )
