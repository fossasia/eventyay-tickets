import logging

import bleach
import dateutil
import uuid
from django.contrib import messages
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _, ngettext_lazy
from django.views.generic import FormView, ListView, TemplateView, UpdateView, View

from pretix.base.email import get_available_placeholders, get_email_context
from pretix.base.i18n import LazyI18nString, language
from pretix.base.models import CachedFile, Event, LogEntry, Order, OrderPosition
from pretix.base.models.event import SubEvent
from pretix.base.services.mail import TolerantDict
from pretix.base.templatetags.rich_text import markdown_compile_email
from pretix.control.permissions import EventPermissionRequiredMixin
from pretix.plugins.sendmail.models import QueuedMail
from pretix.control.views.event import EventSettingsFormView, EventSettingsViewMixin
from .forms import MailContentSettingsForm, MailForm, QueuedMailEditForm, QueuedMailFilterForm, TeamMailForm


logger = logging.getLogger('pretix.plugins.sendmail')


class SenderView(EventPermissionRequiredMixin, FormView):
    template_name = 'pretixplugins/sendmail/send_form.html'
    permission = 'can_change_orders'
    form_class = MailForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        if 'from_log' in self.request.GET:
            try:
                from_log_id = self.request.GET.get('from_log')
                logentry = LogEntry.objects.get(
                    id=from_log_id,
                    event=self.request.event,
                    action_type='pretix.plugins.sendmail.sent',
                )
                kwargs['initial'] = {
                    'recipients': logentry.parsed_data.get('recipients', 'orders'),
                    'message': LazyI18nString(logentry.parsed_data['message']),
                    'subject': LazyI18nString(logentry.parsed_data['subject']),
                    'sendto': logentry.parsed_data['sendto'],
                }
                if 'items' in logentry.parsed_data:
                    kwargs['initial']['items'] = self.request.event.items.filter(
                        id__in=[a['id'] for a in logentry.parsed_data['items']]
                    )
                elif logentry.parsed_data.get('item'):
                    kwargs['initial']['items'] = self.request.event.items.filter(id=logentry.parsed_data['item']['id'])
                if 'checkin_lists' in logentry.parsed_data:
                    kwargs['initial']['checkin_lists'] = self.request.event.checkin_lists.filter(
                        id__in=[c['id'] for c in logentry.parsed_data['checkin_lists']]
                    )
                kwargs['initial']['filter_checkins'] = logentry.parsed_data.get('filter_checkins', False)
                kwargs['initial']['not_checked_in'] = logentry.parsed_data.get('not_checked_in', False)
                if logentry.parsed_data.get('subevents_from'):
                    kwargs['initial']['subevents_from'] = dateutil.parser.parse(logentry.parsed_data['subevents_from'])
                if logentry.parsed_data.get('subevents_to'):
                    kwargs['initial']['subevents_to'] = dateutil.parser.parse(logentry.parsed_data['subevents_to'])
                if logentry.parsed_data.get('created_from'):
                    kwargs['initial']['created_from'] = dateutil.parser.parse(logentry.parsed_data['created_from'])
                if logentry.parsed_data.get('created_to'):
                    kwargs['initial']['created_to'] = dateutil.parser.parse(logentry.parsed_data['created_to'])
                if logentry.parsed_data.get('subevent'):
                    try:
                        kwargs['initial']['subevent'] = self.request.event.subevents.get(
                            pk=logentry.parsed_data['subevent']['id']
                        )
                    except SubEvent.DoesNotExist:
                        pass
            except LogEntry.DoesNotExist:
                raise Http404(_('You supplied an invalid log entry ID'))
        
        import ast
        if 'copyToDraft' in self.request.GET:
            try:
                mail_id = int(self.request.GET.get('copyToDraft'))
                qm = QueuedMail.objects.get(id=mail_id, event=self.request.event)
                kwargs['initial'] = kwargs.get('initial', {})

                def parse_field(raw):
                    try:
                        data = ast.literal_eval(raw) if isinstance(raw, str) else raw
                        if isinstance(data, dict):
                            value = data.get('en') or next(iter(data.values()), '')
                            return value.replace('\r\n', '\n')
                    except Exception:
                        pass
                    return raw.replace('\r\n', '\n') if isinstance(raw, str) else ''

                subject = parse_field(qm.raw_subject)
                message = parse_field(qm.raw_message)

                attachments = []
                if qm.attachments:
                    attachments_qs = CachedFile.objects.filter(id__in=[uuid.UUID(att_id) for att_id in qm.attachments])
                    if attachments_qs.exists():
                        attachments = [attachments_qs.first()]

                kwargs['initial'].update({
                    'subject': subject,
                    'message': message,
                })
                if attachments:
                    kwargs['initial']['attachment'] = attachments[0]
            except (QueuedMail.DoesNotExist, ValueError):
                pass

        return kwargs

    def form_invalid(self, form):
        messages.error(self.request, _('We could not send the email. See below for details.'))
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

        kwargs = {
            'recipients': form.cleaned_data['recipients'],
            'event': self.request.event.pk,
            'user': self.request.user.pk,
            'subject': form.cleaned_data['subject'].data,
            'message': form.cleaned_data['message'].data,
            'orders': [o.pk for o in orders],
            'items': [i.pk for i in form.cleaned_data.get('items')],
            'not_checked_in': form.cleaned_data.get('not_checked_in'),
            'checkin_lists': [i.pk for i in form.cleaned_data.get('checkin_lists')],
            'filter_checkins': form.cleaned_data.get('filter_checkins'),
        }
        if form.cleaned_data.get('attachment') is not None:
            kwargs['attachments'] = [form.cleaned_data['attachment'].id]

        for o in orders:
            if 'orders' in form.cleaned_data['recipients'] or 'both' in form.cleaned_data['recipients']:
                if o.email:
                    with language(o.locale, self.request.event.settings.region):
                        ctx = get_email_context(event=self.request.event, order=o, position_or_address=o.invoice_address)
                        QueuedMail.objects.create(
                            event=self.request.event,
                            user=self.request.user,
                            order=o,
                            recipient=o.email,
                            raw_subject=form.cleaned_data['subject'].data,
                            raw_message=form.cleaned_data['message'].data,
                            subject=form.cleaned_data['subject'].localize(o.locale).format_map(ctx),
                            message=form.cleaned_data['message'].localize(o.locale).format_map(ctx),
                            locale=o.locale,
                            reply_to=self.request.event.settings.get('contact_mail'),
                            bcc=self.request.event.settings.get('mail_bcc'),  # already comma-separated
                            # optionally add attachments
                            attachments=[str(form.cleaned_data['attachment'].id)] if form.cleaned_data.get('attachment') else None,
                        )

            if 'attendees' in form.cleaned_data['recipients'] or 'both' in form.cleaned_data['recipients']:
                for p in o.positions.prefetch_related('addons'):
                    if not p.attendee_email:
                        continue
                    if p.item_id not in [i.pk for i in form.cleaned_data.get('items')]:
                        continue
                    with language(o.locale, self.request.event.settings.region):
                        ctx = get_email_context(event=self.request.event, order=o, position_or_address=p, position=p)
                        QueuedMail.objects.create(
                            event=self.request.event,
                            user=self.request.user,
                            order=o,
                            position=p,
                            recipient=p.attendee_email,
                            raw_subject=form.cleaned_data['subject'].data,
                            raw_message=form.cleaned_data['message'].data,
                            subject=form.cleaned_data['subject'].localize(o.locale).format_map(ctx),
                            message=form.cleaned_data['message'].localize(o.locale).format_map(ctx),
                            locale=o.locale,
                            reply_to=self.request.event.settings.get('contact_mail'),
                            bcc=self.request.event.settings.get('mail_bcc'),  # already comma-separated
                            attachments=[str(form.cleaned_data['attachment'].id)] if form.cleaned_data.get('attachment') else None,
                        )

        messages.success(
            self.request,
            _(
                '%d emails have been saved to the outbox - you can make individual changes there or just send them all.'
            )
            % len(orders),
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


class SentMailView(EventPermissionRequiredMixin, ListView):
    model = QueuedMail
    context_object_name = "mails"
    template_name = "pretixplugins/sendmail/sent_list.html"
    default_filters = (
        "recipient__icontains",
        "subject__icontains",
    )
    default_sort_field = "-created"
    sortable_fields = ("recipient", "subject", "created")
    paginate_by = 25
    permission_required = "can_change_orders"

    def get_filter_form(self):
        return QueuedMailFilterForm(
            self.request.GET, event=self.request.event, sent=True
        )

    def get_queryset(self):
        return (
            self.request.event.queued_mails
            .select_related("user", "order", "position")
            .filter(sent=True)
            .order_by("-created")
        )


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


class OutboxListView(EventPermissionRequiredMixin, ListView):
    model = QueuedMail
    context_object_name = 'mails'
    template_name = 'pretixplugins/sendmail/outbox_list.html'
    permission_required = 'can_change_orders'
    paginate_by = 25

    def get_queryset(self):
        return QueuedMail.objects.filter(event=self.request.event, sent=False).order_by('-created')


class SendAllQueuedMailsView(EventPermissionRequiredMixin, View):
    permission_required = 'can_change_orders'

    def post(self, request, *args, **kwargs):
        mails = QueuedMail.objects.filter(event=request.event, sent=False)
        count = 0
        for mail in mails:
            if mail.send():
                count += 1
        messages.success(request, _('%d mails have been sent.') % count)
        return redirect(reverse('plugins:sendmail:outbox', kwargs={
            'organizer': request.event.organizer.slug,
            'event': request.event.slug
        }))


class SendQueuedMailView(EventPermissionRequiredMixin, View):
    permission_required = 'can_change_orders'

    def post(self, request, *args, **kwargs):
        mail = get_object_or_404(QueuedMail, event=request.event, pk=kwargs['pk'])
        if mail.sent:
            messages.warning(request, _('This mail has already been sent.'))
        else:
            mail.send()
            messages.success(request, _('The mail has been sent.'))
        return redirect(reverse('plugins:sendmail:outbox', kwargs={
            'organizer': request.event.organizer.slug,
            'event': request.event.slug
        }))


class EditQueuedMailView(EventPermissionRequiredMixin, UpdateView):
    model = QueuedMail
    form_class = QueuedMailEditForm
    template_name = 'pretixplugins/sendmail/outbox_form.html'
    permission_required = 'can_change_orders'

    def get_object(self, queryset=None):
        return get_object_or_404(QueuedMail, event=self.request.event, pk=self.kwargs["pk"])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['read_only'] = self.object.sent  # Make the form read-only if already sent

        if self.object.attachments:
            ctx['attachments_files'] = CachedFile.objects.filter(
                id__in=[uuid.UUID(att_id) for att_id in self.object.attachments]
            )
        else:
            ctx['attachments_files'] = []
        return ctx

    def form_valid(self, form):
        if form.instance.sent:
            messages.error(self.request, _('This email has already been sent and cannot be edited.'))
            return self.form_invalid(form)
        
        response = super().form_valid(form)
        
        # Check if "Save and Send" was clicked
        if self.request.POST.get('action') == 'save_and_send':
            if self.object.send():
                messages.success(self.request, _('Your changes have been saved and the email has been sent.'))
            else:
                messages.error(self.request, _('Your changes have been saved, but there was an error sending the email.'))
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
        if mail.sent:
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
        count = QueuedMail.objects.filter(event=self.request.event, sent=False).count()
        return ngettext_lazy(
            "Do you really want to purge this mail?",
            "Do you really want to purge {count} mails?",
            count
        ).format(count=count)

    def post(self, request, *args, **kwargs):
        qs = QueuedMail.objects.filter(event=request.event, sent=False)
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


class ComposeMailChoice(EventPermissionRequiredMixin, TemplateView):
    permission_required = 'can_change_orders'
    template_name = 'pretixplugins/sendmail/compose_choice.html'


class ComposeTeamsMail(EventPermissionRequiredMixin, TemplateView, FormView):
    template_name = 'pretixplugins/sendmail/send_team_form.html'
    permission = 'can_change_orders'
    form_class = TeamMailForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['output'] = getattr(self, 'output', None)
        return ctx

    def form_valid(self, form):
        subject = form.cleaned_data['subject']
        message = form.cleaned_data['message']
        event = self.request.event
        user = self.request.user
        attachment = form.cleaned_data.get('attachment')

        attachment_ids = [str(attachment.id)] if attachment else None

        if self.request.POST.get('action') == 'preview':
            self.output = {}
            for l in event.settings.locales:
                with language(l, event.settings.region):
                    context_dict = {
                        'event': event.name,
                        'team': _('(Team name)'),
                        'name': _('(Recipient name)')
                    }

                    subject_preview = bleach.clean(subject.localize(l), tags=[]).format_map(context_dict)
                    message_preview = message.localize(l).format_map(context_dict)
                    message_preview_html = markdown_compile_email(message_preview)

                    self.output[l] = {
                        'subject': _('Subject: {subject}').format(subject=subject_preview),
                        'html': message_preview_html,
                    }

            return self.get(self.request, *self.args, **self.kwargs)

        sent_emails = set()
        count = 0

        for team in form.cleaned_data['teams']:
            for member in team.members.all():
                if not member.email or member.email in sent_emails:
                    continue

                locale = getattr(member, 'locale', None) or event.locale

                ctx = {
                    'event': event.name,
                    'team': team.name,
                    'name': member.get_display_name() if hasattr(member, 'get_display_name') else member.email,
                }

                QueuedMail.objects.create(
                    event=event,
                    user=user,
                    team=team,
                    recipient=member.email,
                    raw_subject=subject.data,
                    raw_message=message.data,
                    subject=subject.localize(locale).format_map(ctx),
                    message=message.localize(locale).format_map(ctx),
                    locale=locale,
                    reply_to=event.settings.get('contact_mail'),
                    bcc=event.settings.get('mail_bcc'),
                    attachments=attachment_ids,
                )
                sent_emails.add(member.email)
                count += 1

        messages.success(
            self.request,
            _('%d emails have been saved to the outbox - you can make individual changes there or just send them all.') % count
        )

        return redirect(
            'plugins:sendmail:compose_email_teams',
            event=event.slug,
            organizer=event.organizer.slug,
        )
