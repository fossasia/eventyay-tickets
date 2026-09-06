import logging

import nh3
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import OuterRef, Q, Subquery
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext_lazy
from django.views.generic import FormView, ListView, TemplateView, UpdateView, View

from eventyay.base.i18n import language
from i18nfield.strings import LazyI18nString
from eventyay.base.meetup import is_meetup_event
from eventyay.base.models.base import CachedFile
from eventyay.base.models.event import Event
from eventyay.base.models.orders import OrderPosition
from eventyay.base.services.mail import expand_email_variable_chips, mail
from eventyay.base.templatetags.rich_text import (
    build_email_preview_context,
    compile_email_body,
)
from eventyay.common.mail import get_reply_to_address
from eventyay.control.permissions import EventPermissionRequiredMixin, event_permission_required
from eventyay.control.views.event import EventSettingsFormView, EventSettingsViewMixin
from eventyay.helpers.timezone import format_scheduled_datetime
from eventyay.plugins.sendmail.forms import EmailQueueEditForm
from eventyay.plugins.sendmail.mixins import (
    CopyDraftMixin,
    QueryFilterOrderingMixin,
    ensure_draft_defaults,
)
from eventyay.plugins.sendmail.models import ComposingFor, EmailQueue, EmailQueueFilter, EmailQueueToUser
from eventyay.plugins.sendmail.tasks import send_queued_mail

from . import forms
from .forms import MailContentSettingsForm, TeamMailForm, TicketMailRecipientsForm


logger = logging.getLogger(__name__)

@event_permission_required('can_change_orders')
def attendees_select2(request, **kwargs):
    query = request.GET.get('query', '')
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1

    qs = OrderPosition.objects.filter(
        order__event=request.event,
        canceled=False
    ).select_related('order')

    if query:
        qs = qs.filter(
            Q(attendee_name_cached__icontains=query) |
            Q(attendee_email__icontains=query) |
            Q(order__code__icontains=query)
        )

    qs = qs.order_by('attendee_name_cached', 'order__code')

    total = qs.count()
    pagesize = 20
    offset = (page - 1) * pagesize

    doc = {
        'results': [
            {
                'id': op.pk,
                'text': f"{op.attendee_name_cached or op.attendee_email or op.order.code} ({op.order.code})",
            }
            for op in qs[offset : offset + pagesize]
        ],
        'pagination': {'more': total >= (offset + pagesize)},
    }
    return JsonResponse(doc)


class TicketMailRecipients(EventPermissionRequiredMixin, View):
    """Returns the audience matching the ticket mail filters in the query string."""

    permission = 'can_change_orders'

    def get(self, request, *args, **kwargs):
        form = TicketMailRecipientsForm(event=request.event, data=request.GET)
        if not form.is_valid():
            return JsonResponse({'error': form.errors, 'count': 0, 'recipients': []}, status=400)

        try:
            recipients = form.get_recipient_preview()
        except Exception:
            logger.exception('Failed to build ticket mail recipient preview')
            return JsonResponse(
                {'error': 'preview_failed', 'count': 0, 'recipients': []},
                status=500,
            )

        return JsonResponse(
            {
                'count': len(recipients),
                'recipients': recipients,
            }
        )




class TeamMailRecipients(EventPermissionRequiredMixin, View):
    permission = 'can_change_orders'

    def get(self, request, *args, **kwargs):
        from .forms import TeamMailRecipientsForm
        form = TeamMailRecipientsForm(event=request.event, data=request.GET)
        if not form.is_valid():
            return JsonResponse({'error': form.errors, 'count': 0, 'recipients': []}, status=400)

        try:
            recipients = form.get_recipient_preview(user=request.user)
        except Exception as e:
            logger.exception('Failed to build team mail recipient preview: %s', e)
            return JsonResponse(
                {'error': 'preview_failed', 'count': 0, 'recipients': []},
                status=500,
            )

        return JsonResponse(
            {
                'count': len(recipients),
                'recipients': recipients,
            }
        )

class BulkReplyToMixin:
    """Mixin for bulk email views to resolve Reply-To address."""

    def _get_reply_to_for_bulk_email(self):
        event = self.request.event
        sender = event.settings.get('mail_from') if event else settings.DEFAULT_FROM_EMAIL
        sender = sender or settings.DEFAULT_FROM_EMAIL
        return get_reply_to_address(event, sender_email=sender)


class ComposeMailChoice(EventPermissionRequiredMixin, TemplateView):
    permission_required = 'can_change_orders'
    template_name = 'pretixplugins/sendmail/compose_choice.html'


class SenderView(EventPermissionRequiredMixin, CopyDraftMixin, BulkReplyToMixin, FormView):
    template_name = 'pretixplugins/sendmail/send_form.html'
    permission = 'can_change_orders'
    form_class = forms.MailForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        kwargs['draft_save'] = self.request.POST.get('action') == 'draft'
        self.load_copy_draft(self.request, kwargs)

        if self.request.method == 'POST' and self.request.POST.get('action') == 'draft':
            data = kwargs.get('data')
            if data is not None:
                kwargs['data'] = ensure_draft_defaults(data)

        return kwargs

    def form_valid(self, form):
        action = self.request.POST.get('action')
        is_draft = action == 'draft'

        if is_draft:
            if not form.cleaned_data.get('subject'):
                form.cleaned_data['subject'] = LazyI18nString({self.request.event.settings.locale or 'en': str(_('Untitled draft'))})
            if not form.cleaned_data.get('text'):
                form.cleaned_data['text'] = LazyI18nString({self.request.event.settings.locale or 'en': ''})
            if not form.cleaned_data.get('products'):
                form.cleaned_data['products'] = []

        if action == 'test':
            test_email = form.cleaned_data.get('test_email')
            if not test_email:
                form.add_error('test_email', _('Please enter a test email address.'))
                return self.form_invalid(form)

            try:
                context_dict = build_email_preview_context(
                    self.request.event, ['event', 'order', 'position_or_address']
                )

                mail(
                    email=test_email,
                    subject=form.cleaned_data['subject'],
                    template=form.cleaned_data['text'],
                    context=context_dict,
                    event=self.request.event,
                    locale=self.request.event.settings.locale,
                    sender=self._get_reply_to_for_bulk_email() or self.request.event.settings.get('mail_from'),
                    event_bcc=self.request.event.settings.get('mail_bcc'),
                    user=self.request.user,
                    auto_email=False,
                    sync_send=True,
                    attach_cached_files=[form.cleaned_data['attachment'].id] if form.cleaned_data.get('attachment') else [],
                )
                messages.success(self.request, _('Test email sent successfully to {email}.').format(email=test_email))
            except Exception as e:
                logger.exception("Failed to send test email")
                messages.error(self.request, _('Failed to send test email: {error}').format(error=str(e)))

            return self.render_to_response(self.get_context_data(form=form))

        if form.cleaned_data.get('recipients') == 'individual':
            individual_attendees = form.cleaned_data.get('individual_attendees')
            if not individual_attendees and not is_draft:
                form.add_error('individual_attendees', _('Please select at least one attendee.'))
                return self.form_invalid(form)
            orders = form.resolve_orders()
        else:
            orders = form.resolve_orders()

        if not orders and not is_draft:
            messages.error(self.request, _('There are no orders matching this selection.'))
            return self.get(self.request, *self.args, **self.kwargs)

        if action == 'preview':
            self.output = {}
            self.mail_count = orders.count()
            for l in self.request.event.settings.locales:
                with language(l, self.request.event.settings.region):
                    context_dict = build_email_preview_context(
                        self.request.event, ['event', 'order', 'position_or_address']
                    )
                    subject = nh3.clean(form.cleaned_data['subject'].localize(l), tags=set())
                    preview_subject = nh3.clean(subject.format_map(context_dict), tags=set())
                    message = form.cleaned_data['text'].localize(l)
                    message_preview = expand_email_variable_chips(
                        message.format_map(context_dict), dict(context_dict)
                    )
                    preview_text = compile_email_body(message_preview)

                    self.output[l] = {
                        'subject': _('Subject: {subject}').format(subject=preview_subject),
                        'html': preview_text,
                    }

            return self.get(self.request, *self.args, **self.kwargs)

        scheduled_at = form.cleaned_data.get('scheduled_at')
        draft_id = self.request.POST.get('draft_id') or getattr(self, 'draft_id', None)

        qm = None
        if draft_id:
            qm = EmailQueue.objects.filter(
                pk=draft_id,
                event=self.request.event,
                composing_for=ComposingFor.ATTENDEES,
                is_draft=True,
            ).first()

        subject_val = form.cleaned_data['subject'].data if hasattr(form.cleaned_data['subject'], 'data') else form.cleaned_data['subject']
        message_val = form.cleaned_data['text'].data if hasattr(form.cleaned_data['text'], 'data') else form.cleaned_data['text']
        attachment = form.cleaned_data.get('attachment')
        attachment_ids = [] if is_draft or not attachment else [attachment.id]

        if qm:
            qm.subject = subject_val
            qm.message = message_val
            qm.attachments = attachment_ids
            qm.reply_to = form.cleaned_data.get('reply_to') or self._get_reply_to_for_bulk_email() or ''
            qm.bcc = form.cleaned_data.get('bcc') or self.request.event.settings.get('mail_bcc') or ''
            qm.scheduled_at = scheduled_at
            qm.is_draft = is_draft
            qm.save()

            qmf, created = EmailQueueFilter.objects.get_or_create(mail=qm)
            qmf.recipients = form.cleaned_data.get('recipients', 'orders')
            qmf.order_status = form.cleaned_data.get('order_status', [])
            qmf.orders = list(orders.values_list('pk', flat=True))
            qmf.products = [i.pk for i in form.cleaned_data.get('products', [])]
            qmf.checkin_lists = [cl.pk for cl in form.cleaned_data.get('checkin_lists', [])]
            qmf.has_filter_checkins = bool(form.cleaned_data.get('has_filter_checkins'))
            qmf.not_checked_in = bool(form.cleaned_data.get('not_checked_in'))
            qmf.subevent = form.cleaned_data.get('subevent').pk if form.cleaned_data.get('subevent') else None
            qmf.subevents_from = form.cleaned_data.get('subevents_from')
            qmf.subevents_to = form.cleaned_data.get('subevents_to')
            qmf.order_created_from = form.cleaned_data.get('order_created_from')
            qmf.order_created_to = form.cleaned_data.get('order_created_to')
            qmf.individual_attendees = [a.pk for a in form.cleaned_data.get('individual_attendees', [])] if form.cleaned_data.get('individual_attendees') else []
            qmf.save()
        else:
            qm = EmailQueue.objects.create(
                event=self.request.event,
                user=self.request.user,
                subject=subject_val,
                message=message_val,
                attachments=attachment_ids,
                locale=self.request.event.settings.locale,
                reply_to=form.cleaned_data.get('reply_to') or self._get_reply_to_for_bulk_email() or '',
                bcc=form.cleaned_data.get('bcc') or self.request.event.settings.get('mail_bcc') or '',
                composing_for=ComposingFor.ATTENDEES,
                scheduled_at=scheduled_at,
                is_draft=is_draft,
            )

            EmailQueueFilter.objects.create(
                mail=qm,
                recipients=form.cleaned_data.get('recipients', 'orders'),
                order_status=form.cleaned_data.get('order_status', []),
                orders=list(orders.values_list('pk', flat=True)),
                products=[i.pk for i in form.cleaned_data.get('products', [])],
                checkin_lists=[cl.pk for cl in form.cleaned_data.get('checkin_lists', [])],
                has_filter_checkins=bool(form.cleaned_data.get('has_filter_checkins')),
                not_checked_in=bool(form.cleaned_data.get('not_checked_in')),
                subevent=form.cleaned_data.get('subevent').pk if form.cleaned_data.get('subevent') else None,
                subevents_from=form.cleaned_data.get('subevents_from'),
                subevents_to=form.cleaned_data.get('subevents_to'),
                order_created_from=form.cleaned_data.get('order_created_from'),
                order_created_to=form.cleaned_data.get('order_created_to'),
                individual_attendees=[a.pk for a in form.cleaned_data.get('individual_attendees', [])] if form.cleaned_data.get('individual_attendees') else []
            )

        qm.populate_to_users()

        if is_draft and form.cleaned_data.get('attachment'):
            messages.info(
                self.request,
                _('Attachments are not saved in drafts. Please reattach files before sending.')
            )

        if is_draft:
            messages.success(self.request, _('The draft has been saved.'))
            return redirect(
                'control:event.mail.drafts',
                event=self.request.event.slug,
                organizer=self.request.event.organizer.slug,
            )

        if scheduled_at:
            send_queued_mail.apply_async(args=[self.request.event.pk, qm.pk], eta=scheduled_at)
            self.request.event.log_action(
                'eventyay.sendmail.scheduled',
                user=self.request.user,
                data={'email_queue_id': qm.pk, 'scheduled_at': scheduled_at.isoformat()},
            )
            messages.success(
                self.request,
                _('Your email has been scheduled for {datetime} ({timezone}).').format(
                    datetime=format_scheduled_datetime(self.request.event, scheduled_at),
                    timezone=self.request.event.timezone,
                )
            )
        else:
            messages.success(
                self.request,
                _('Your email has been added to the outbox.')
            )

        return redirect(
            'control:event.mail.outbox',
            event=self.request.event.slug,
            organizer=self.request.event.organizer.slug,
        )

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['output'] = getattr(self, 'output', None)
        ctx['mail_count'] = getattr(self, 'mail_count', 0)
        ctx['draft_id'] = getattr(self, 'draft_id', self.request.POST.get('draft_id', None))
        ctx['recipient_count'] = getattr(self, 'recipient_count', 0)
        ctx['is_draft'] = bool(ctx['draft_id'])
        return ctx


class MailTemplatesView(EventSettingsViewMixin, EventSettingsFormView):
    model = Event
    template_name = 'pretixplugins/sendmail/mail_templates.html'
    form_class = MailContentSettingsForm
    permission = 'can_change_event_settings'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_meetup_event'] = is_meetup_event(self.request.event)
        return context

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
                'eventyay.event.settings',
                user=self.request.user,
                data={k: form.cleaned_data.get(k) for k in form.changed_data},
            )
        messages.success(self.request, _('Your changes have been saved.'))
        return redirect(reverse(
            'control:event.mail.templates',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        ))


class OutboxListView(EventPermissionRequiredMixin, QueryFilterOrderingMixin, ListView):
    model = EmailQueue
    context_object_name = 'mails'
    template_name = 'pretixplugins/sendmail/outbox_list.html'
    permission_required = 'can_change_orders'
    paginate_by = 25

    def get_template_names(self):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return ['pretixplugins/sendmail/outbox_list_content.html']
        return super().get_template_names()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        query = self.request.GET.get('q', '')
        ordering = self.request.GET.get('ordering')

        ctx['headers'] = [
            ('subject', _('Subject')),
            ('recipient', _('To')),
        ]
        ctx['current_ordering'] = ordering
        ctx['query'] = query
        ctx['pending_mail_count'] = ctx['paginator'].count

        MAX_ERRORS_TO_SHOW = 2
        for mail in ctx['mails']:
            mail.recipient_emails_display = ", ".join(mail.get_recipient_emails())
            all_recipients = mail.recipients.all()
            errors = [r for r in all_recipients if r.error]
            mail.recipient_errors_preview = errors[:MAX_ERRORS_TO_SHOW]
            mail.recipient_error_count = len(errors)

        return ctx

    def get_queryset(self):
        first_recipient_email = EmailQueueToUser.objects.filter(
            mail=OuterRef('pk')
        ).order_by('id').values('email')[:1]

        base_qs = self.model.objects.filter(
            event=self.request.event,
            sent_at__isnull=True,
            is_draft=False
        ).select_related('event', 'user').prefetch_related('recipients').annotate(
            first_recipient_email=Subquery(first_recipient_email)
        )

        return self.get_filtered_queryset(base_qs)


class DraftsListView(OutboxListView):
    template_name = 'pretixplugins/sendmail/draft_list.html'

    def get_queryset(self):
        first_recipient_email = EmailQueueToUser.objects.filter(
            mail=OuterRef('pk')
        ).order_by('id').values('email')[:1]

        base_qs = self.model.objects.filter(
            event=self.request.event,
            sent_at__isnull=True,
            is_draft=True
        ).select_related('event', 'user').prefetch_related('recipients').annotate(
            first_recipient_email=Subquery(first_recipient_email)
        )

        return self.get_filtered_queryset(base_qs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['pending_mail_count'] = self.request.event.email_queue.filter(
            sent_at__isnull=True, is_draft=True
        ).count()
        ctx['is_drafts'] = True
        ctx['headers'] = [
            ('subject', _('Subject')),
            ('type', _('Email type')),
            ('recipient', _('Recipients')),
            ('scheduled', _('Scheduled for')),
            ('created', _('Last modified')),
        ]
        return ctx


class DuplicateDraftView(EventPermissionRequiredMixin, View):
    permission_required = 'can_change_orders'

    def post(self, request, *args, **kwargs):
        mail = get_object_or_404(
            EmailQueue,
            event=request.event,
            pk=kwargs['pk'],
            is_draft=True,
        )
        mail.duplicate()
        messages.success(request, _('The draft has been duplicated.'))
        return redirect(
            'control:event.mail.drafts',
            event=request.event.slug,
            organizer=request.event.organizer.slug,
        )

class SendEmailQueueView(EventPermissionRequiredMixin, View):
    permission_required = 'can_change_orders'

    def post(self, request, *args, **kwargs):
        mail = get_object_or_404(
            EmailQueue,
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
                _('The mail has been queued for sending.')
            )

        return HttpResponseRedirect(reverse('control:event.mail.outbox', kwargs={
            'organizer': request.event.organizer.slug,
            'event': request.event.slug,
        }))


class EditEmailQueueView(EventPermissionRequiredMixin, UpdateView):
    model = EmailQueue
    form_class = EmailQueueEditForm
    template_name = 'pretixplugins/sendmail/outbox_form.html'
    permission_required = 'can_change_orders'

    def get_object(self, queryset=None):
        return get_object_or_404(
            EmailQueue, event=self.request.event, pk=self.kwargs["pk"]
        )

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.is_draft and request.method == 'GET':
            return redirect(obj.get_edit_url())
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        kwargs['read_only'] = bool(self.object.sent_at)

        if self.request.method == 'POST' and self.request.POST.get('action') == 'draft':
            data = kwargs.get('data')
            if data is not None:
                kwargs['data'] = ensure_draft_defaults(data)

        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['read_only'] = bool(self.object.sent_at)

        if self.object.attachments:
            ctx['attachments_files'] = CachedFile.objects.filter(
                id__in=self.object.attachments
            )
        else:
            ctx['attachments_files'] = []

        ctx['output'] = getattr(self, 'output', None)

        return ctx

    def form_invalid(self, form):
        messages.error(self.request, _('We could not save the email. See below for details.'))
        return super().form_invalid(form)

    def form_valid(self, form):
        if form.instance.sent_at:
            messages.error(self.request, _('This email has already been sent and cannot be edited.'))
            return self.form_invalid(form)

        if self.request.POST.get('action') == 'preview':
            self.output = {}
            event = self.request.event
            subject = form.cleaned_data.get('subject')
            if not subject:
                subject = LazyI18nString({self.request.event.settings.locale or 'en': ''})
            message = form.cleaned_data.get('text') or form.cleaned_data.get('message')
            if not message:
                message = LazyI18nString({self.request.event.settings.locale or 'en': ''})

            if form.instance.composing_for == ComposingFor.TEAMS:
                base_placeholders = ['event', 'user', 'team']
            else:
                base_placeholders = ['event', 'order', 'position_or_address']

            for l in event.settings.locales:
                with language(l, event.settings.region):
                    context_dict = build_email_preview_context(event, base_placeholders)

                    try:
                        subject_preview = nh3.clean(
                            subject.localize(l).format_map(context_dict),
                            tags=set(),
                        )
                    except KeyError as e:
                        form.add_error('subject', _('Invalid placeholder(s): {}').format(str(e)))
                        return self.form_invalid(form)

                    try:
                        message_preview = expand_email_variable_chips(
                            message.localize(l).format_map(context_dict),
                            dict(context_dict),
                        )
                    except KeyError as e:
                        error_field = 'text' if 'text' in form.fields else 'message'
                        form.add_error(error_field, _('Invalid placeholder(s): {}').format(str(e)))
                        return self.form_invalid(form)

                    self.output[l] = {
                        'subject': _('Subject: {subject}').format(subject=subject_preview),
                        'html': compile_email_body(message_preview),
                    }

            return self.get(self.request, *self.args, **self.kwargs)

        if self.request.POST.get('action') == 'draft':
            form.instance.is_draft = True
        else:
            form.instance.is_draft = False

        response = super().form_valid(form)
        
        if form.instance.is_draft:
            messages.success(self.request, _('The draft has been updated.'))
            return redirect(
                'control:event.mail.drafts',
                event=self.request.event.slug,
                organizer=self.request.event.organizer.slug,
            )

        if form.instance.scheduled_at:
            send_queued_mail.apply_async(
                args=[self.request.event.pk, form.instance.pk],
                eta=form.instance.scheduled_at,
            )

        messages.success(self.request, _('Your changes have been saved.'))
        return response

    def get_success_url(self):
        return reverse('control:event.mail.outbox', kwargs={
            'organizer': self.request.event.organizer.slug,
            'event': self.request.event.slug
        })


class DeleteEmailQueueView(EventPermissionRequiredMixin, TemplateView):
    permission_required = 'can_change_orders'
    template_name = 'pretixplugins/sendmail/delete_confirmation.html'

    @cached_property
    def mail(self):
        return get_object_or_404(
            EmailQueue, event=self.request.event, pk=self.kwargs['pk']
        )

    def question(self):
        if self.mail.is_draft:
            return _('Do you really want to delete this draft?')
        return _('Do you really want to delete this mail?')

    def post(self, request, *args, **kwargs):
        mail = self.mail
        is_draft = mail.is_draft
        if mail.sent_at:
            messages.error(
                request,
                _("This mail has already been sent and cannot be deleted.")
            )
        else:
            EmailQueueFilter.objects.filter(mail=mail).delete()
            EmailQueueToUser.objects.filter(mail=mail).delete()
            mail.delete()

            if is_draft:
                messages.success(
                    request,
                    _("The draft has been deleted.")
                )
            else:
                messages.success(
                    request,
                    _("The mail and its related data have been deleted.")
                )

        if is_draft:
            return redirect(reverse('control:event.mail.drafts', kwargs={
                'organizer': request.event.organizer.slug,
                'event': request.event.slug
            }))
        return redirect(reverse('control:event.mail.outbox', kwargs={
            'organizer': request.event.organizer.slug,
            'event': request.event.slug
        }))


class PurgeEmailQueuesView(EventPermissionRequiredMixin, TemplateView):
    permission_required = 'can_change_orders'
    template_name = 'pretixplugins/sendmail/purge_confirmation.html'

    def get_permission_object(self):
        return self.request.event

    def question(self):
        count = EmailQueue.objects.filter(event=self.request.event, sent_at__isnull=True, is_draft=False).count()
        return ngettext_lazy(
            "Do you really want to purge the mail?",
            "Do you really want to purge {count} mails?",
            count
        ).format(count=count)

    def post(self, request, *args, **kwargs):
        mails = EmailQueue.objects.filter(event=request.event, sent_at__isnull=True, is_draft=False)

        EmailQueueFilter.objects.filter(mail__in=mails).delete()
        EmailQueueToUser.objects.filter(mail__in=mails).delete()
        count = mails.count()
        mails.delete()

        messages.success(
            request,
            ngettext_lazy(
                "One mail has been discarded.",
                "{count} mails have been discarded.",
                count
            ).format(count=count)
        )

        return redirect(reverse('control:event.mail.outbox', kwargs={
            'organizer': request.event.organizer.slug,
            'event': request.event.slug
        }))


class PurgeDraftsView(EventPermissionRequiredMixin, TemplateView):
    permission_required = 'can_change_orders'
    template_name = 'pretixplugins/sendmail/purge_confirmation.html'

    def get_permission_object(self):
        return self.request.event

    def question(self):
        count = EmailQueue.objects.filter(event=self.request.event, sent_at__isnull=True, is_draft=True).count()
        return ngettext_lazy(
            "Do you really want to discard the draft?",
            "Do you really want to discard {count} drafts?",
            count
        ).format(count=count)

    def post(self, request, *args, **kwargs):
        mails = EmailQueue.objects.filter(event=request.event, sent_at__isnull=True, is_draft=True)

        EmailQueueFilter.objects.filter(mail__in=mails).delete()
        EmailQueueToUser.objects.filter(mail__in=mails).delete()
        count = mails.count()
        mails.delete()

        messages.success(
            request,
            ngettext_lazy(
                "One draft has been discarded.",
                "{count} drafts have been discarded.",
                count
            ).format(count=count)
        )

        return redirect(reverse('control:event.mail.drafts', kwargs={
            'organizer': request.event.organizer.slug,
            'event': request.event.slug
        }))



class SentMailView(EventPermissionRequiredMixin, QueryFilterOrderingMixin, ListView):
    model = EmailQueue
    context_object_name = "mails"
    template_name = "pretixplugins/sendmail/sent_list.html"
    permission_required = "can_change_orders"
    paginate_by = 25

    def get_queryset(self):
        first_recipient_email = EmailQueueToUser.objects.filter(
            mail=OuterRef('pk')
        ).order_by('pk').values('email')[:1]

        base_qs = self.model.objects.filter(
            event=self.request.event,
            sent_at__isnull=False
        ).select_related('event', 'user').prefetch_related('recipients').annotate(
            first_recipient_email=Subquery(first_recipient_email)
        )

        return self.get_filtered_queryset(base_qs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        query = self.request.GET.get('q', '')
        ordering = self.request.GET.get('ordering')

        ctx['headers'] = [
            ('subject', _('Subject')),
            ('recipient', _('To')),
            ('created', _('Sent at')),
        ]
        ctx['current_ordering'] = ordering
        ctx['query'] = query

        MAX_RECIPIENTS_TO_SHOW = 3
        for mail in ctx['mails']:
            users = EmailQueueToUser.objects.filter(mail=mail).order_by('pk')[:MAX_RECIPIENTS_TO_SHOW]
            mail.recipient_preview = [u.email or u.user_display or u.order_code for u in users]
            mail.recipient_total = EmailQueueToUser.objects.filter(mail=mail).count()

        return ctx


class ComposeTeamsMail(EventPermissionRequiredMixin, CopyDraftMixin, BulkReplyToMixin, FormView):
    template_name = 'pretixplugins/sendmail/send_team_form.html'
    permission = 'can_change_orders'
    form_class = TeamMailForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        kwargs['draft_save'] = self.request.POST.get('action') == 'draft'
        self.load_copy_draft(self.request, kwargs, team_mode=True)

        if self.request.method == 'POST' and self.request.POST.get('action') == 'draft':
            data = kwargs.get('data')
            if data is not None:
                kwargs['data'] = ensure_draft_defaults(data)

        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['output'] = getattr(self, 'output', None)
        ctx['draft_id'] = getattr(self, 'draft_id', self.request.POST.get('draft_id', None))
        ctx['recipient_count'] = getattr(self, 'recipient_count', 0)
        ctx['is_draft'] = bool(ctx['draft_id'])
        return ctx

    def form_invalid(self, form):
        messages.error(self.request, _('We could not save the email. See below for details.'))
        return super().form_invalid(form)

    def form_valid(self, form):
        is_draft = self.request.POST.get('action') == 'draft'

        if is_draft:
            if not form.cleaned_data.get('subject'):
                form.cleaned_data['subject'] = LazyI18nString({self.request.event.settings.locale or 'en': str(_('Untitled draft'))})
            if not form.cleaned_data.get('message'):
                form.cleaned_data['message'] = LazyI18nString({self.request.event.settings.locale or 'en': ''})
            if not form.cleaned_data.get('teams'):
                form.cleaned_data['teams'] = []

        event = self.request.event
        user = self.request.user

        if self.request.POST.get('action') == 'test':
            test_email = form.cleaned_data.get('test_email')
            if not test_email:
                form.add_error('test_email', _('Please enter a test email address.'))
                return self.form_invalid(form)

            try:
                context_dict = build_email_preview_context(
                    event, ['event', 'user', 'team']
                )

                mail(
                    email=test_email,
                    subject=form.cleaned_data['subject'],
                    template=form.cleaned_data['message'],
                    context=context_dict,
                    event=event,
                    locale=event.settings.locale,
                    sender=event.settings.get('mail_from'),
                    event_reply_to=form.cleaned_data.get('reply_to') or self._get_reply_to_for_bulk_email(),
                    event_bcc=form.cleaned_data.get('bcc') or event.settings.get('mail_bcc'),
                    user=user,
                    auto_email=False,
                    sync_send=True,
                    attach_cached_files=[form.cleaned_data['attachment'].id] if form.cleaned_data.get('attachment') else [],
                )
                messages.success(self.request, _('Test email sent successfully to {email}.').format(email=test_email))
            except Exception as e:
                logger.exception("Failed to send test email")
                messages.error(self.request, _('Failed to send test email: {error}').format(error=str(e)))

            return self.render_to_response(self.get_context_data(form=form))
        subject = form.cleaned_data['subject']
        message = form.cleaned_data['message']

        self.output = {}
        for l in event.settings.locales:
            with language(l, event.settings.region):
                context_dict = build_email_preview_context(event, ['event', 'user', 'team'])

                try:
                    subject_preview = nh3.clean(
                        subject.localize(l).format_map(context_dict),
                        tags=set(),
                    )
                except KeyError as e:
                    form.add_error('subject', _('Invalid placeholder(s): {}').format(str(e)))
                    return self.form_invalid(form)

                try:
                    message_preview = expand_email_variable_chips(
                        message.localize(l).format_map(context_dict),
                        dict(context_dict),
                    )
                except KeyError as e:
                    form.add_error('message', _('Invalid placeholder(s): {}').format(str(e)))
                    return self.form_invalid(form)

                if self.request.POST.get('action') == 'preview':
                    self.output[l] = {
                        'subject': _('Subject: {subject}').format(subject=subject_preview),
                        'html': compile_email_body(message_preview),
                    }

        if self.request.POST.get('action') == 'preview':
            return self.get(self.request, *self.args, **self.kwargs)

        recipients_list = []
        try:
            preview_recipients = form.get_recipient_preview(user=user)
            for r in preview_recipients:
                recipients_list.append({
                    "email": r['email'],
                    "team": None,
                    "orders": [],
                    "positions": [],
                    "products": [],
                    "sent": False,
                    "error": None
                })
        except Exception:
            logger.exception("Failed to build team mail recipients list")
            form.add_error(None, _('An error occurred while resolving recipients.'))
            return self.form_invalid(form)

        if not recipients_list and not is_draft:
            messages.error(self.request, _('There are no valid recipients for the selected teams.'))
            return self.form_invalid(form)

        scheduled_at = form.cleaned_data.get('scheduled_at')
        draft_id = self.request.POST.get('draft_id') or getattr(self, 'draft_id', None)

        mail_instance = None
        if draft_id:
            mail_instance = EmailQueue.objects.filter(
                pk=draft_id,
                event=event,
                composing_for=ComposingFor.TEAMS,
                is_draft=True,
            ).first()

        subject_val = subject.data if hasattr(subject, 'data') else subject
        message_val = message.data if hasattr(message, 'data') else message
        attachment = form.cleaned_data.get('attachment')
        attachment_ids = [] if is_draft or not attachment else [attachment.id]

        reply_to_val = form.cleaned_data.get('reply_to') or self._get_reply_to_for_bulk_email() or ''
        bcc_val = form.cleaned_data.get('bcc') or event.settings.get('mail_bcc') or ''

        if mail_instance:
            mail_instance.subject = subject_val
            mail_instance.message = message_val
            mail_instance.attachments = attachment_ids
            mail_instance.reply_to = reply_to_val
            mail_instance.bcc = bcc_val
            mail_instance.scheduled_at = scheduled_at
            mail_instance.is_draft = is_draft
            mail_instance.save()

            qmf, created = EmailQueueFilter.objects.get_or_create(mail=mail_instance)
            qmf.teams = [team.pk for team in form.cleaned_data.get('teams', [])]
            qmf.team_role = form.cleaned_data.get('team_role', '')
            qmf.permission_level = form.cleaned_data.get('permission_level', '')
            qmf.status = form.cleaned_data.get('status', '')
            qmf.specific_people = [u.pk for u in form.cleaned_data.get('specific_people', [])]
            qmf.exclude_me = bool(form.cleaned_data.get('exclude_me', False))
            qmf.save()
        else:
            mail_instance = EmailQueue.objects.create(
                event=event,
                user=user,
                composing_for=ComposingFor.TEAMS,
                subject=subject_val,
                message=message_val,
                locale=event.settings.locale,
                reply_to=reply_to_val,
                bcc=bcc_val,
                attachments=attachment_ids,
                scheduled_at=scheduled_at,
                is_draft=is_draft,
            )

            EmailQueueFilter.objects.create(
                mail=mail_instance,
                order_status=[],
                products=[],
                checkin_lists=[],
                has_filter_checkins=False,
                not_checked_in=False,
                subevent=None,
                subevents_from=None,
                subevents_to=None,
                order_created_from=None,
                order_created_to=None,
                orders=[],
                teams=[team.pk for team in form.cleaned_data.get('teams', [])],
                team_role=form.cleaned_data.get('team_role', ''),
                permission_level=form.cleaned_data.get('permission_level', ''),
                status=form.cleaned_data.get('status', ''),
                specific_people=[u.pk for u in form.cleaned_data.get('specific_people', [])],
                exclude_me=bool(form.cleaned_data.get('exclude_me', False)),
            )

        mail_instance.recipients.all().delete()
        recipient_objs = [
            EmailQueueToUser(
                mail=mail_instance,
                email=rec["email"],
                team=rec["team"],
                sent=rec["sent"],
                error=rec["error"]
            )
            for rec in recipients_list
        ]
        if recipient_objs:
            EmailQueueToUser.objects.bulk_create(recipient_objs)

        if is_draft and form.cleaned_data.get('attachment'):
            messages.info(
                self.request,
                _('Attachments are not saved in drafts. Please reattach files before sending.')
            )

        if is_draft:
            messages.success(self.request, _('The draft has been saved.'))
            return redirect(
                'control:event.mail.drafts',
                event=event.slug,
                organizer=event.organizer.slug,
            )

        if scheduled_at:
            send_queued_mail.apply_async(args=[event.pk, mail_instance.pk], eta=scheduled_at)
            event.log_action(
                'eventyay.sendmail.scheduled',
                user=user,
                data={'email_queue_id': mail_instance.pk, 'scheduled_at': scheduled_at.isoformat()},
            )
            messages.success(
                self.request,
                _('Your email has been scheduled for {datetime} ({timezone}).').format(
                    datetime=format_scheduled_datetime(event, scheduled_at),
                    timezone=event.timezone,
                )
            )
        else:
            messages.success(
                self.request,
                _('Your email has been added to the outbox.')
            )

        return redirect(
            'control:event.mail.outbox',
            event=event.slug,
            organizer=event.organizer.slug,
        )
