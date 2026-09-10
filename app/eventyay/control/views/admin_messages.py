import json
import logging

from allauth.account.models import EmailAddress
from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.timezone import now as tz_now
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import FormView, ListView, TemplateView
from django_scopes import scopes_disabled

from eventyay.base.models import Event, LogEntry, Organizer, User
from eventyay.base.models.admin_mail import (
    AdminEmailQueue,
    AdminEmailQueueFilter,
    AdminEmailQueueRecipient,
    AdminEmailStatus,
    AdminRecipientGroup,
)
from eventyay.base.models.organizer import Team
from eventyay.control.forms.admin.admin_messages import (
    AdminComposeForm,
    AdminComposeRecipientsForm,
)
from eventyay.control.permissions import AdministratorPermissionRequiredMixin
from eventyay.control.views import PaginationMixin

logger = logging.getLogger(__name__)

HIGH_RECIPIENT_THRESHOLD = 500


def resolve_admin_recipients(filters: dict) -> list[dict]:
    """
    Resolve recipients based on admin filter criteria.
    Returns a deduplicated list of dicts with user_id, email, name, reason, status, role.
    Attendee emails without a matching User record are included with user_id=None.
    """
    recipient_group = filters.get('recipient_group', AdminRecipientGroup.ALL_USERS)
    account_status = filters.get('account_status', '')
    user_role = filters.get('user_role', '')
    language = filters.get('language', '')
    event_status = filters.get('event_status', '')
    created_after = filters.get('created_after')
    created_before = filters.get('created_before')
    last_active_after = filters.get('last_active_after')
    last_active_before = filters.get('last_active_before')
    selected_organiser_ids = filters.get('selected_organisers', [])
    selected_event_ids = filters.get('selected_events', [])
    selected_user_ids = filters.get('selected_users', [])
    exclude_admins = filters.get('exclude_admins', False)
    exclude_inactive = filters.get('exclude_inactive', False)
    exclude_unconfirmed = filters.get('exclude_unconfirmed_email', False)

    qs = User.objects.exclude(email__isnull=True).exclude(email='').exclude(deleted=True)

    if exclude_inactive:
        qs = qs.filter(is_active=True)
    if exclude_admins:
        qs = qs.filter(is_staff=False, is_administrator=False)

    if account_status == 'active':
        qs = qs.filter(is_active=True)
    elif account_status == 'banned':
        qs = qs.filter(moderation_state='banned')
    elif account_status == 'verified':
        verified_ids = EmailAddress.objects.filter(
            verified=True, primary=True
        ).values_list('user_id', flat=True)
        qs = qs.filter(pk__in=verified_ids)
    elif account_status == 'unverified':
        verified_ids = EmailAddress.objects.filter(
            verified=True, primary=True
        ).values_list('user_id', flat=True)
        qs = qs.exclude(pk__in=verified_ids)

    if user_role == 'admin':
        qs = qs.filter(Q(is_staff=True) | Q(is_administrator=True))
    elif user_role == 'staff':
        qs = qs.filter(is_staff=True)
    elif user_role == 'organiser':
        qs = qs.filter(teams__isnull=False).distinct()
    elif user_role == 'user':
        qs = qs.filter(teams__isnull=True, is_staff=False, is_administrator=False)

    if language:
        qs = qs.filter(locale=language)

    if created_after:
        qs = qs.filter(date_joined__gte=created_after)
    if created_before:
        qs = qs.filter(date_joined__lte=created_before)
    if last_active_after:
        qs = qs.filter(last_login__gte=last_active_after)
    if last_active_before:
        qs = qs.filter(last_login__lte=last_active_before)

    if exclude_unconfirmed:
        confirmed_ids = EmailAddress.objects.filter(
            verified=True, primary=True
        ).values_list('user_id', flat=True)
        qs = qs.filter(pk__in=confirmed_ids)

    extra_emails: set[str] = set()

    with scopes_disabled():
        if recipient_group == AdminRecipientGroup.ALL_USERS:
            pass

        elif recipient_group == AdminRecipientGroup.ALL_ORGANISERS:
            qs = qs.filter(teams__isnull=False).distinct()

        elif recipient_group == AdminRecipientGroup.EVENT_ORGANISERS:
            if selected_event_ids:
                qs = qs.filter(
                    Q(teams__all_events=True, teams__organizer__events__pk__in=selected_event_ids)
                    | Q(teams__limit_events__pk__in=selected_event_ids)
                ).distinct()
            elif selected_organiser_ids:
                qs = qs.filter(teams__organizer__pk__in=selected_organiser_ids).distinct()
            else:
                qs = qs.filter(teams__isnull=False).distinct()

        elif recipient_group == AdminRecipientGroup.EVENT_TEAM_MEMBERS:
            team_filter = Q(teams__isnull=False)
            if selected_event_ids:
                team_filter = Q(
                    Q(teams__all_events=True, teams__organizer__events__pk__in=selected_event_ids)
                    | Q(teams__limit_events__pk__in=selected_event_ids)
                )
            elif selected_organiser_ids:
                team_filter = Q(teams__organizer__pk__in=selected_organiser_ids)
            qs = qs.filter(team_filter).distinct()

        elif recipient_group == AdminRecipientGroup.SPEAKERS:
            from eventyay.base.models.submission import Submission
            speaker_qs = Submission.objects.all()
            if selected_event_ids:
                speaker_qs = speaker_qs.filter(event__pk__in=selected_event_ids)
            speaker_user_ids = speaker_qs.values_list('speakers__pk', flat=True).distinct()
            qs = qs.filter(pk__in=speaker_user_ids)

        elif recipient_group == AdminRecipientGroup.REVIEWERS:
            qs = qs.filter(teams__is_reviewer=True).distinct()
            if selected_event_ids:
                qs = qs.filter(
                    Q(teams__all_events=True, teams__organizer__events__pk__in=selected_event_ids)
                    | Q(teams__limit_events__pk__in=selected_event_ids)
                ).distinct()

        elif recipient_group == AdminRecipientGroup.ATTENDEES:
            from eventyay.base.models.orders import Order, OrderPosition
            pos_qs = OrderPosition.objects.filter(
                attendee_email__isnull=False
            ).exclude(attendee_email='')
            if selected_event_ids:
                pos_qs = pos_qs.filter(order__event__pk__in=selected_event_ids)
            attendee_email_set = set(
                pos_qs.values_list('attendee_email', flat=True).distinct()
            )
            order_qs = Order.objects.filter(
                status__in=['p', 'n']
            ).exclude(email__isnull=True).exclude(email='')
            if selected_event_ids:
                order_qs = order_qs.filter(event__pk__in=selected_event_ids)
            attendee_email_set.update(
                order_qs.values_list('email', flat=True).distinct()
            )
            all_user_emails = set(
                qs.filter(email__in=attendee_email_set).values_list('email', flat=True)
            )
            extra_emails = {e.strip().lower() for e in attendee_email_set} - {e.lower() for e in all_user_emails}
            qs = qs.filter(email__in=attendee_email_set)

        elif recipient_group == AdminRecipientGroup.SELECTED_USERS:
            if selected_user_ids:
                qs = qs.filter(pk__in=selected_user_ids)
            else:
                qs = qs.none()

    if event_status and recipient_group in (
        AdminRecipientGroup.EVENT_ORGANISERS,
        AdminRecipientGroup.EVENT_TEAM_MEMBERS,
        AdminRecipientGroup.SPEAKERS,
        AdminRecipientGroup.REVIEWERS,
        AdminRecipientGroup.ATTENDEES,
    ):
        n = tz_now()
        with scopes_disabled():
            if event_status == 'live':
                event_pks = list(Event.objects.filter(live=True).values_list('pk', flat=True))
            elif event_status == 'draft':
                event_pks = list(Event.objects.filter(live=False).values_list('pk', flat=True))
            elif event_status == 'past':
                event_pks = list(Event.objects.filter(
                    Q(date_to__lt=n) | Q(date_to__isnull=True, date_from__lt=n)
                ).values_list('pk', flat=True))
            else:
                event_pks = None

            if event_pks is not None:
                if recipient_group in (
                    AdminRecipientGroup.EVENT_ORGANISERS,
                    AdminRecipientGroup.EVENT_TEAM_MEMBERS,
                    AdminRecipientGroup.REVIEWERS,
                ):
                    qs = qs.filter(
                        Q(teams__all_events=True, teams__organizer__events__pk__in=event_pks)
                        | Q(teams__limit_events__pk__in=event_pks)
                    ).distinct()

                elif recipient_group == AdminRecipientGroup.SPEAKERS:
                    from eventyay.base.models.submission import Submission
                    speaker_ids = Submission.objects.filter(
                        event__pk__in=event_pks
                    ).values_list('speakers__pk', flat=True).distinct()
                    qs = qs.filter(pk__in=speaker_ids)

                elif recipient_group == AdminRecipientGroup.ATTENDEES:
                    from eventyay.base.models.orders import Order, OrderPosition
                    filtered_pos_emails = set(
                        OrderPosition.objects.filter(
                            order__event__pk__in=event_pks,
                            attendee_email__isnull=False,
                        ).exclude(attendee_email='').values_list('attendee_email', flat=True).distinct()
                    )
                    filtered_order_emails = set(
                        Order.objects.filter(
                            event__pk__in=event_pks,
                            status__in=['p', 'n'],
                        ).exclude(email__isnull=True).exclude(email='').values_list('email', flat=True).distinct()
                    )
                    event_emails = filtered_pos_emails | filtered_order_emails
                    qs = qs.filter(email__in=event_emails)
                    extra_emails = {e.strip().lower() for e in event_emails} - {
                        e.strip().lower() for e in qs.values_list('email', flat=True)
                    }

    seen: set[str] = set()
    result: list[dict] = []
    reason = str(dict(AdminRecipientGroup.choices).get(recipient_group, recipient_group))

    for user in qs.only('pk', 'email', 'fullname', 'is_active', 'is_staff', 'is_administrator'):
        email_lower = user.email.strip().lower()
        if email_lower in seen:
            continue
        seen.add(email_lower)

        role = 'Admin' if (user.is_administrator or user.is_staff) else 'User'
        result.append({
            'user_id': user.pk,
            'email': user.email,
            'name': user.get_full_name() or user.email,
            'status': 'Active' if user.is_active else 'Inactive',
            'role': role,
            'reason': reason,
        })

    for email in extra_emails:
        if email not in seen:
            seen.add(email)
            result.append({
                'user_id': None,
                'email': email,
                'name': email,
                'status': '',
                'role': _('Attendee'),
                'reason': reason,
            })

    return result


def _extract_filter_dict(form_data: dict) -> dict:
    filters = {
        'recipient_group': form_data.get('recipient_group', AdminRecipientGroup.ALL_USERS),
        'account_status': form_data.get('account_status', ''),
        'user_role': form_data.get('user_role', ''),
        'language': form_data.get('language', ''),
        'event_status': form_data.get('event_status', ''),
        'created_after': form_data.get('created_after'),
        'created_before': form_data.get('created_before'),
        'last_active_after': form_data.get('last_active_after'),
        'last_active_before': form_data.get('last_active_before'),
        'exclude_admins': form_data.get('exclude_admins', False),
        'exclude_inactive': form_data.get('exclude_inactive', False),
        'exclude_unconfirmed_email': form_data.get('exclude_unconfirmed_email', False),
    }

    for key in ('selected_organisers', 'selected_events', 'selected_users'):
        val = form_data.get(key)
        if val:
            if hasattr(val, 'values_list'):
                filters[key] = list(val.values_list('pk', flat=True))
            else:
                filters[key] = [int(x) for x in str(val).split(',') if x.strip().isdigit()]
        else:
            filters[key] = []

    return filters


def _save_filters(mail: AdminEmailQueue, filters: dict) -> AdminEmailQueueFilter:
    obj, _ = AdminEmailQueueFilter.objects.update_or_create(
        mail=mail,
        defaults={
            'account_status': filters.get('account_status', ''),
            'user_role': filters.get('user_role', ''),
            'language': filters.get('language', ''),
            'created_after': filters.get('created_after'),
            'created_before': filters.get('created_before'),
            'last_active_after': filters.get('last_active_after'),
            'last_active_before': filters.get('last_active_before'),
            'event_status': filters.get('event_status', ''),
            'event_ids': filters.get('selected_events', []),
            'organiser_ids': filters.get('selected_organisers', []),
            'selected_user_ids': filters.get('selected_users', []),
            'exclude_admins': filters.get('exclude_admins', False),
            'exclude_inactive': filters.get('exclude_inactive', False),
            'exclude_unconfirmed_email': filters.get('exclude_unconfirmed_email', False),
        },
    )
    return obj


def _populate_recipients(mail: AdminEmailQueue, recipients: list[dict]) -> int:
    mail.recipients.all().delete()

    objs = []
    seen: set[str] = set()
    for r in recipients:
        email_lower = r['email'].strip().lower()
        if email_lower in seen:
            continue
        seen.add(email_lower)
        objs.append(AdminEmailQueueRecipient(
            mail=mail,
            user_id=r.get('user_id'),
            email=r['email'],
            name=r.get('name', ''),
            reason=r.get('reason', ''),
        ))

    if objs:
        AdminEmailQueueRecipient.objects.bulk_create(objs, ignore_conflicts=True)

    return len(objs)


PLACEHOLDER_GROUPS = {
    'user': [
        {'key': 'user_name', 'label': _('Full name')},
        {'key': 'first_name', 'label': _('First name')},
        {'key': 'last_name', 'label': _('Last name')},
        {'key': 'email', 'label': _('Email address')},
        {'key': 'account_url', 'label': _('Account URL')},
    ],
    'organiser': [
        {'key': 'organiser_name', 'label': _('Organiser name')},
        {'key': 'organiser_url', 'label': _('Organiser URL')},
    ],
    'event': [
        {'key': 'event_name', 'label': _('Event name')},
        {'key': 'event_url', 'label': _('Event URL')},
        {'key': 'event_start_date', 'label': _('Event start date')},
        {'key': 'event_end_date', 'label': _('Event end date')},
    ],
    'platform': [
        {'key': 'platform_name', 'label': _('Platform name')},
        {'key': 'platform_url', 'label': _('Platform URL')},
        {'key': 'support_email', 'label': _('Support email')},
        {'key': 'support_url', 'label': _('Support URL')},
    ],
}

SAMPLE_CONTEXT = {
    'user_name': 'Jane Doe',
    'first_name': 'Jane',
    'last_name': 'Doe',
    'email': 'jane@example.com',
    'account_url': '#',
    'organiser_name': 'Example Organiser',
    'organiser_url': '#',
    'event_name': 'Example Event',
    'event_url': '#',
    'event_start_date': '2026-01-15',
    'event_end_date': '2026-01-17',
    'platform_name': 'Eventyay',
    'platform_url': '#',
    'support_email': 'support@eventyay.com',
    'support_url': '#',
}


class AdminMessageComposeView(AdministratorPermissionRequiredMixin, FormView):
    template_name = 'pretixcontrol/admin/messages/compose.html'
    form_class = AdminComposeForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['draft_save'] = self.request.POST.get('action') == 'draft'
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        draft_pk = self.request.GET.get('draft')
        if draft_pk:
            draft = AdminEmailQueue.objects.filter(
                pk=draft_pk, status__in=[AdminEmailStatus.DRAFT, AdminEmailStatus.QUEUED]
            ).first()
            if draft:
                self._draft = draft
                initial.update({
                    'recipient_group': draft.recipient_group,
                    'subject': draft.subject,
                    'message': draft.message,
                    'reply_to': draft.reply_to,
                    'bcc': draft.bcc,
                    'scheduled_at': draft.scheduled_at,
                    'delivery_mode': 'later' if draft.scheduled_at else 'now',
                })
                try:
                    f = draft.filters
                    initial.update({
                        'account_status': f.account_status,
                        'user_role': f.user_role,
                        'language': f.language,
                        'event_status': f.event_status,
                        'created_after': f.created_after,
                        'created_before': f.created_before,
                        'last_active_after': f.last_active_after,
                        'last_active_before': f.last_active_before,
                        'exclude_admins': f.exclude_admins,
                        'exclude_inactive': f.exclude_inactive,
                        'exclude_unconfirmed_email': f.exclude_unconfirmed_email,
                    })
                    if f.organiser_ids:
                        initial['selected_organisers'] = Organizer.objects.filter(pk__in=f.organiser_ids)
                    if f.event_ids:
                        initial['selected_events'] = Event.objects.filter(pk__in=f.event_ids)
                    if f.selected_user_ids:
                        initial['selected_users'] = User.objects.filter(pk__in=f.selected_user_ids)
                except AdminEmailQueueFilter.DoesNotExist:
                    pass

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['draft'] = getattr(self, '_draft', None)
        ctx['output'] = getattr(self, 'output', None)
        ctx['recipient_count'] = getattr(self, 'recipient_count', 0)
        ctx['placeholders'] = PLACEHOLDER_GROUPS
        draft = ctx['draft']
        if draft and draft.recipient_count_snapshot:
            current = resolve_admin_recipients(_extract_filter_dict(ctx['form'].initial))
            if len(current) != draft.recipient_count_snapshot:
                ctx['recipient_count_changed'] = True
                ctx['old_recipient_count'] = draft.recipient_count_snapshot
                ctx['new_recipient_count'] = len(current)
        return ctx

    def form_valid(self, form):
        action = self.request.POST.get('action')
        cd = form.cleaned_data
        filters = _extract_filter_dict(cd)

        if action == 'test':
            test_email = cd.get('test_email')
            if not test_email:
                form.add_error('test_email', _('Please enter a test email address.'))
                return self.form_invalid(form)
            return self._send_test_email(form, test_email)

        if action == 'preview':
            recipients = resolve_admin_recipients(filters)
            self.recipient_count = len(recipients)
            self.output = self._build_preview(cd)
            return self.render_to_response(self.get_context_data(form=form))

        is_draft = action == 'draft'

        draft = getattr(self, '_draft', None)
        draft_pk = self.request.POST.get('draft_id') or self.request.GET.get('draft')
        if draft_pk and not draft:
            draft = AdminEmailQueue.objects.filter(
                pk=draft_pk, status__in=[AdminEmailStatus.DRAFT, AdminEmailStatus.QUEUED]
            ).first()

        attachment = cd.get('attachment')

        if draft:
            mail = draft
            mail.recipient_group = cd['recipient_group']
            mail.subject = cd.get('subject', '')
            mail.message = cd.get('message', '')
            mail.reply_to = cd.get('reply_to', '')
            mail.bcc = cd.get('bcc', '')
            mail.attachment = attachment.id if attachment else None
            mail.scheduled_at = cd.get('scheduled_at')
            mail.status = AdminEmailStatus.DRAFT if is_draft else AdminEmailStatus.QUEUED
            mail.user = self.request.user
        else:
            mail = AdminEmailQueue(
                user=self.request.user,
                recipient_group=cd['recipient_group'],
                subject=cd.get('subject', ''),
                message=cd.get('message', ''),
                reply_to=cd.get('reply_to', ''),
                bcc=cd.get('bcc', ''),
                attachment=attachment.id if attachment else None,
                scheduled_at=cd.get('scheduled_at'),
                status=AdminEmailStatus.DRAFT if is_draft else AdminEmailStatus.QUEUED,
            )

        if is_draft:
            resolved = resolve_admin_recipients(filters)
            mail.recipient_count_snapshot = len(resolved)
            mail.save()
            _save_filters(mail, filters)
            messages.success(self.request, _('The draft has been saved.'))
            return redirect('eventyay_admin:admin.messages.drafts')

        resolved = resolve_admin_recipients(filters)
        count = len(resolved)

        if count >= HIGH_RECIPIENT_THRESHOLD and not self.request.POST.get('confirm_send'):
            self.recipient_count = count
            ctx = self.get_context_data(form=form)
            ctx['confirm_high_count'] = True
            ctx['high_count'] = count
            return self.render_to_response(ctx)

        mail.recipient_count_snapshot = count
        with transaction.atomic():
            mail.save()
            _save_filters(mail, filters)
            _populate_recipients(mail, resolved)

        LogEntry.objects.create(
            content_type=ContentType.objects.get_for_model(AdminEmailQueue),
            object_id=mail.pk,
            user=self.request.user,
            action_type='eventyay.admin.mail.queued',
            data=json.dumps({
                'admin_email_id': mail.pk,
                'recipient_count': count,
                'subject': mail.subject,
                'recipient_group': mail.recipient_group,
                'send_immediately': cd.get('send_immediately', False),
                'scheduled_at': mail.scheduled_at.isoformat() if mail.scheduled_at else None,
            }),
        )

        from eventyay.control.tasks import send_admin_email

        send_immediately = cd.get('send_immediately', False)
        if send_immediately:
            send_admin_email.apply_async(args=[mail.pk])
            messages.success(self.request, _('Your email is being sent to {count} recipients.').format(count=count))
        elif mail.scheduled_at:
            send_admin_email.apply_async(args=[mail.pk], eta=mail.scheduled_at)
            messages.success(
                self.request,
                _('Your email has been scheduled for {count} recipients.').format(count=count),
            )
        else:
            messages.success(
                self.request,
                _('Your email has been added to the outbox with {count} recipients.').format(count=count),
            )

        return redirect('eventyay_admin:admin.messages.outbox')

    def _send_test_email(self, form, test_email: str):
        from eventyay.common.mail import mail_send_task

        cd = form.cleaned_data
        subject = cd.get('subject', _('(No subject)'))
        body = cd.get('message', '')

        sample = dict(SAMPLE_CONTEXT)
        sample['email'] = test_email
        for key, value in sample.items():
            subject = subject.replace('{' + key + '}', value)
            body = body.replace('{' + key + '}', value)

        try:
            mail_send_task.apply_async(
                kwargs={
                    'to': [test_email],
                    'subject': f'[TEST] {subject}',
                    'body': body,
                    'html': AdminEmailQueue.make_html(body),
                    'reply_to': [cd.get('reply_to')] if cd.get('reply_to') else [],
                    'event': None,
                    'cc': [],
                    'bcc': [],
                    'attachments': None,
                },
                ignore_result=True,
            )
            messages.success(
                self.request,
                _('Test email sent successfully to {email}.').format(email=test_email),
            )
        except Exception:
            logger.exception('Failed to send test email')
            messages.error(
                self.request,
                _('Failed to send test email. Please check your mail configuration.'),
            )

        return self.render_to_response(self.get_context_data(form=form))

    def _build_preview(self, cd: dict) -> dict:
        subject = cd.get('subject', '')
        body = cd.get('message', '')
        for key, value in SAMPLE_CONTEXT.items():
            subject = subject.replace('{' + key + '}', value)
            body = body.replace('{' + key + '}', value)

        return {
            'subject': subject,
            'html': AdminEmailQueue.make_html(body),
        }


class AdminMessageOutboxView(AdministratorPermissionRequiredMixin, PaginationMixin, ListView):
    model = AdminEmailQueue
    template_name = 'pretixcontrol/admin/messages/outbox.html'
    context_object_name = 'mails'
    paginate_by = 25

    def get_queryset(self):
        return (
            AdminEmailQueue.objects
            .filter(status=AdminEmailStatus.QUEUED)
            .annotate(recipient_count=Count('recipients'))
            .select_related('user')
            .order_by('-created_at')
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['pending_count'] = AdminEmailQueue.objects.filter(status=AdminEmailStatus.QUEUED).count()
        return ctx


class AdminMessageDraftsView(AdministratorPermissionRequiredMixin, PaginationMixin, ListView):
    model = AdminEmailQueue
    template_name = 'pretixcontrol/admin/messages/drafts.html'
    context_object_name = 'mails'
    paginate_by = 25

    def get_queryset(self):
        return (
            AdminEmailQueue.objects
            .filter(status=AdminEmailStatus.DRAFT)
            .annotate(recipient_count=Count('recipients'))
            .select_related('user')
            .order_by('-updated_at')
        )


class AdminMessageSentView(AdministratorPermissionRequiredMixin, PaginationMixin, ListView):
    model = AdminEmailQueue
    template_name = 'pretixcontrol/admin/messages/sent.html'
    context_object_name = 'mails'
    paginate_by = 25

    def get_queryset(self):
        return (
            AdminEmailQueue.objects
            .filter(status=AdminEmailStatus.SENT)
            .annotate(recipient_count=Count('recipients'))
            .select_related('user')
            .order_by('-sent_at')
        )


class AdminMessageTemplatesView(AdministratorPermissionRequiredMixin, TemplateView):
    template_name = 'pretixcontrol/admin/messages/templates.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['templates'] = self._get_platform_templates()
        return ctx

    def _get_platform_templates(self) -> list[dict]:
        from eventyay.base.models.mail import MailTemplate, MailTemplateRoles

        templates = []
        for role_value, role_label in MailTemplateRoles.choices:
            templates.append({
                'name': str(role_label),
                'category': _('System'),
                'trigger': str(role_label),
                'recipient_type': _('User'),
                'role': role_value,
            })

        system_templates = [
            {'name': _('Account registration'), 'category': _('Account'), 'trigger': _('User registers')},
            {'name': _('Email confirmation'), 'category': _('Account'), 'trigger': _('Email verification sent')},
            {'name': _('Password reset'), 'category': _('Account'), 'trigger': _('Password reset requested')},
            {'name': _('Account notification'), 'category': _('Account'), 'trigger': _('Account status changed')},
            {'name': _('Organiser invitation'), 'category': _('Team'), 'trigger': _('Team invitation sent')},
            {'name': _('Event team invitation'), 'category': _('Team'), 'trigger': _('Event team invitation sent')},
            {'name': _('Billing validation'), 'category': _('Billing'), 'trigger': _('Billing validation requested')},
            {'name': _('Platform fee notification'), 'category': _('Billing'), 'trigger': _('Fee invoiced')},
            {'name': _('Ticket order confirmation'), 'category': _('Ticketing'), 'trigger': _('Order placed')},
            {'name': _('Ticket confirmation'), 'category': _('Ticketing'), 'trigger': _('Ticket confirmed')},
            {'name': _('Ticket cancellation'), 'category': _('Ticketing'), 'trigger': _('Order cancelled')},
            {'name': _('Refund notification'), 'category': _('Ticketing'), 'trigger': _('Refund processed')},
            {'name': _('CfP submission confirmation'), 'category': _('CfP'), 'trigger': _('Proposal submitted')},
            {'name': _('Proposal acceptance'), 'category': _('CfP'), 'trigger': _('Proposal accepted')},
            {'name': _('Proposal rejection'), 'category': _('CfP'), 'trigger': _('Proposal rejected')},
            {'name': _('Speaker schedule update'), 'category': _('Schedule'), 'trigger': _('Schedule updated')},
            {'name': _('Reviewer notification'), 'category': _('Review'), 'trigger': _('Review assigned')},
            {'name': _('Team member notification'), 'category': _('Team'), 'trigger': _('Team membership changed')},
            {'name': _('Video/event notification'), 'category': _('Video'), 'trigger': _('Video event updated')},
            {'name': _('System notification'), 'category': _('System'), 'trigger': _('System event')},
        ]
        for t in system_templates:
            t.setdefault('recipient_type', _('User'))
            t.setdefault('role', '')
        templates.extend(system_templates)

        return templates


class AdminMessageTemplateDetailView(AdministratorPermissionRequiredMixin, TemplateView):
    template_name = 'pretixcontrol/admin/messages/template_detail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        role = self.kwargs.get('role', '')
        from eventyay.base.models.mail import MailTemplate, MailTemplateRoles

        template = MailTemplate.objects.filter(role=role).first()
        ctx['mail_template'] = template
        ctx['role'] = role
        ctx['role_label'] = dict(MailTemplateRoles.choices).get(role, role)
        return ctx


class AdminMessageSendView(AdministratorPermissionRequiredMixin, View):
    def post(self, request, pk):
        mail = get_object_or_404(AdminEmailQueue, pk=pk)

        if mail.status == AdminEmailStatus.SENT:
            messages.warning(request, _('This email has already been sent.'))
        elif mail.status == AdminEmailStatus.DRAFT:
            messages.warning(request, _('Drafts cannot be sent directly. Move to outbox first.'))
        else:
            from eventyay.control.tasks import send_admin_email
            send_admin_email.apply_async(args=[mail.pk])
            messages.success(request, _('The email has been queued for sending.'))

        return redirect('eventyay_admin:admin.messages.outbox')


class AdminMessageCancelView(AdministratorPermissionRequiredMixin, View):
    def post(self, request, pk):
        with transaction.atomic():
            mail = (
                AdminEmailQueue.objects
                .select_for_update()
                .filter(pk=pk, status=AdminEmailStatus.QUEUED)
                .first()
            )
            if mail is None:
                messages.warning(request, _('This email could not be cancelled (not found or already processed).'))
                return redirect('eventyay_admin:admin.messages.outbox')

            mail.status = AdminEmailStatus.CANCELLED
            mail.save(update_fields=['status'])

        LogEntry.objects.create(
            content_type=ContentType.objects.get_for_model(AdminEmailQueue),
            object_id=mail.pk,
            user=request.user,
            action_type='eventyay.admin.mail.cancelled',
            data=json.dumps({'admin_email_id': mail.pk, 'subject': mail.subject}),
        )

        messages.success(request, _('The email has been cancelled.'))
        return redirect('eventyay_admin:admin.messages.outbox')


class AdminMessageDeleteView(AdministratorPermissionRequiredMixin, View):
    def post(self, request, pk):
        mail = get_object_or_404(AdminEmailQueue, pk=pk, status=AdminEmailStatus.DRAFT)
        mail.delete()
        messages.success(request, _('The draft has been deleted.'))
        return redirect('eventyay_admin:admin.messages.drafts')


class AdminMessageDuplicateView(AdministratorPermissionRequiredMixin, View):
    def post(self, request, pk):
        mail = get_object_or_404(AdminEmailQueue, pk=pk)
        new_mail = mail.duplicate()
        messages.success(request, _('The email has been duplicated as a draft.'))
        return redirect(new_mail.get_edit_url())


class AdminMessageRecipientsView(AdministratorPermissionRequiredMixin, View):
    def get(self, request):
        form = AdminComposeRecipientsForm(data=request.GET)
        if not form.is_valid():
            return JsonResponse({'count': 0, 'recipients': [], 'errors': form.errors}, status=400)

        filters = _extract_filter_dict(form.cleaned_data)
        recipients = resolve_admin_recipients(filters)

        preview = [
            {
                'name': r['name'],
                'email': r['email'],
                'status': r.get('status', ''),
                'role': r.get('role', ''),
                'reason': r.get('reason', ''),
            }
            for r in recipients[:100]
        ]

        no_email_count = sum(1 for r in recipients if not r.get('email'))
        return JsonResponse({
            'count': len(recipients),
            'skipped': no_email_count,
            'recipients': preview,
        })
