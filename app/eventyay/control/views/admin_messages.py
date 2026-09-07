import logging

from django.contrib import messages
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import FormView, ListView, TemplateView
from django_scopes import scopes_disabled

from eventyay.base.models import LogEntry
from eventyay.base.models.admin_mail import (
    AdminEmailQueue,
    AdminEmailQueueFilter,
    AdminEmailQueueRecipient,
    AdminEmailStatus,
    AdminRecipientGroup,
)
from eventyay.control.forms.admin.admin_messages import (
    AdminComposeForm,
    AdminComposeRecipientsForm,
)
from eventyay.control.permissions import AdministratorPermissionRequiredMixin
from eventyay.control.views import PaginationMixin

logger = logging.getLogger(__name__)


def resolve_admin_recipients(filters: dict) -> list[dict]:
    """
    Resolve recipients based on admin filter criteria.

    Returns a deduplicated list of dicts:
        [{'user_id': int|None, 'email': str, 'name': str, 'reason': str}, ...]
    """
    from allauth.account.models import EmailAddress

    from eventyay.base.models import Event, Organizer, User
    from eventyay.base.models.organizer import Team

    recipient_group = filters.get('recipient_group', AdminRecipientGroup.ALL_USERS)
    account_status = filters.get('account_status', '')
    user_role = filters.get('user_role', '')
    language = filters.get('language', '')
    event_status = filters.get('event_status', '')
    created_after = filters.get('created_after')
    created_before = filters.get('created_before')
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
        verified_user_ids = EmailAddress.objects.filter(
            verified=True, primary=True
        ).values_list('user_id', flat=True)
        qs = qs.filter(pk__in=verified_user_ids)
    elif account_status == 'unverified':
        verified_user_ids = EmailAddress.objects.filter(
            verified=True, primary=True
        ).values_list('user_id', flat=True)
        qs = qs.exclude(pk__in=verified_user_ids)

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

    if exclude_unconfirmed:
        confirmed_user_ids = EmailAddress.objects.filter(
            verified=True, primary=True
        ).values_list('user_id', flat=True)
        qs = qs.filter(pk__in=confirmed_user_ids)

    with scopes_disabled():
        if recipient_group == AdminRecipientGroup.ALL_USERS:
            pass  # No additional filter

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
            speaker_user_ids = Submission.objects.values_list('speakers__pk', flat=True).distinct()
            if selected_event_ids:
                speaker_user_ids = Submission.objects.filter(
                    event__pk__in=selected_event_ids
                ).values_list('speakers__pk', flat=True).distinct()
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
            attendee_emails = OrderPosition.objects.filter(
                attendee_email__isnull=False
            ).exclude(attendee_email='')
            if selected_event_ids:
                attendee_emails = attendee_emails.filter(order__event__pk__in=selected_event_ids)
            attendee_email_list = set(
                attendee_emails.values_list('attendee_email', flat=True).distinct()
            )
            order_emails = Order.objects.filter(
                status__in=['p', 'n']  # paid or pending
            ).exclude(email__isnull=True).exclude(email='')
            if selected_event_ids:
                order_emails = order_emails.filter(event__pk__in=selected_event_ids)
            attendee_email_list.update(
                order_emails.values_list('email', flat=True).distinct()
            )
            qs = qs.filter(email__in=attendee_email_list)

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
        from django.utils.timezone import now as tz_now
        n = tz_now()
        with scopes_disabled():
            if event_status == 'live':
                live_events = Event.objects.filter(live=True).values_list('pk', flat=True)
                qs = qs.filter(
                    Q(teams__all_events=True, teams__organizer__events__pk__in=live_events)
                    | Q(teams__limit_events__pk__in=live_events)
                ).distinct()
            elif event_status == 'draft':
                draft_events = Event.objects.filter(live=False).values_list('pk', flat=True)
                qs = qs.filter(
                    Q(teams__all_events=True, teams__organizer__events__pk__in=draft_events)
                    | Q(teams__limit_events__pk__in=draft_events)
                ).distinct()
            elif event_status == 'past':
                past_events = Event.objects.filter(
                    Q(date_to__lt=n) | Q(date_to__isnull=True, date_from__lt=n)
                ).values_list('pk', flat=True)
                qs = qs.filter(
                    Q(teams__all_events=True, teams__organizer__events__pk__in=past_events)
                    | Q(teams__limit_events__pk__in=past_events)
                ).distinct()

    seen = set()
    result = []
    reason = str(dict(AdminRecipientGroup.choices).get(recipient_group, recipient_group))

    for user in qs.only('pk', 'email', 'fullname', 'is_active', 'is_staff', 'is_administrator'):
        email_lower = user.email.strip().lower()
        if email_lower in seen:
            continue
        seen.add(email_lower)

        role = 'User'
        if user.is_administrator or user.is_staff:
            role = 'Admin'

        result.append({
            'user_id': user.pk,
            'email': user.email,
            'name': user.get_full_name() or user.email,
            'status': 'Active' if user.is_active else 'Inactive',
            'role': role,
            'reason': reason,
        })

    return result


def _extract_filter_dict(form_data: dict) -> dict:
    """Extract filter dict from cleaned form data for resolve_admin_recipients."""
    filters = {
        'recipient_group': form_data.get('recipient_group', AdminRecipientGroup.ALL_USERS),
        'account_status': form_data.get('account_status', ''),
        'user_role': form_data.get('user_role', ''),
        'language': form_data.get('language', ''),
        'event_status': form_data.get('event_status', ''),
        'created_after': form_data.get('created_after'),
        'created_before': form_data.get('created_before'),
        'exclude_admins': form_data.get('exclude_admins', False),
        'exclude_inactive': form_data.get('exclude_inactive', False),
        'exclude_unconfirmed_email': form_data.get('exclude_unconfirmed_email', False),
    }

    selected_organisers = form_data.get('selected_organisers')
    if selected_organisers:
        if hasattr(selected_organisers, 'values_list'):
            filters['selected_organisers'] = list(selected_organisers.values_list('pk', flat=True))
        else:
            filters['selected_organisers'] = [int(x) for x in str(selected_organisers).split(',') if x.strip()]
    else:
        filters['selected_organisers'] = []

    selected_events = form_data.get('selected_events')
    if selected_events:
        if hasattr(selected_events, 'values_list'):
            filters['selected_events'] = list(selected_events.values_list('pk', flat=True))
        else:
            filters['selected_events'] = [int(x) for x in str(selected_events).split(',') if x.strip()]
    else:
        filters['selected_events'] = []

    selected_users = form_data.get('selected_users')
    if selected_users:
        if hasattr(selected_users, 'values_list'):
            filters['selected_users'] = list(selected_users.values_list('pk', flat=True))
        else:
            filters['selected_users'] = [int(x) for x in str(selected_users).split(',') if x.strip()]
    else:
        filters['selected_users'] = []

    return filters


def _save_filters(mail: AdminEmailQueue, filters: dict) -> AdminEmailQueueFilter:
    """Save or update the filter record for an AdminEmailQueue."""
    obj, _ = AdminEmailQueueFilter.objects.update_or_create(
        mail=mail,
        defaults={
            'account_status': filters.get('account_status', ''),
            'user_role': filters.get('user_role', ''),
            'language': filters.get('language', ''),
            'created_after': filters.get('created_after'),
            'created_before': filters.get('created_before'),
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
    """Populate AdminEmailQueueRecipient from resolved list. Returns count."""
    mail.recipients.all().delete()

    objs = []
    seen = set()
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


class AdminMessageComposeView(AdministratorPermissionRequiredMixin, FormView):
    """Compose a platform-wide email."""

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
                pk=draft_pk, status=AdminEmailStatus.DRAFT
            ).first()
            if draft:
                self._draft = draft
                initial.update({
                    'recipient_group': draft.recipient_group,
                    'subject': draft.subject,
                    'message': draft.message,
                    'reply_to': draft.reply_to,
                    'bcc': draft.bcc,
                })
                filters = getattr(draft, 'filters', None)
                if filters:
                    initial.update({
                        'account_status': filters.account_status,
                        'user_role': filters.user_role,
                        'language': filters.language,
                        'event_status': filters.event_status,
                        'created_after': filters.created_after,
                        'created_before': filters.created_before,
                        'exclude_admins': filters.exclude_admins,
                        'exclude_inactive': filters.exclude_inactive,
                        'exclude_unconfirmed_email': filters.exclude_unconfirmed_email,
                    })
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['draft'] = getattr(self, '_draft', None)
        ctx['output'] = getattr(self, 'output', None)
        ctx['recipient_count'] = getattr(self, 'recipient_count', 0)
        ctx['placeholders'] = self._get_placeholders()
        return ctx

    def _get_placeholders(self) -> dict[str, list[dict]]:
        return {
            'user': [
                {'key': 'user_name', 'label': _('Full name')},
                {'key': 'first_name', 'label': _('First name')},
                {'key': 'last_name', 'label': _('Last name')},
                {'key': 'email', 'label': _('Email address')},
                {'key': 'account_url', 'label': _('Account URL')},
            ],
            'platform': [
                {'key': 'platform_name', 'label': _('Platform name')},
                {'key': 'platform_url', 'label': _('Platform URL')},
                {'key': 'support_email', 'label': _('Support email')},
                {'key': 'support_url', 'label': _('Support URL')},
            ],
        }

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

        recipients = resolve_admin_recipients(filters) if not is_draft else []

        draft = getattr(self, '_draft', None)
        draft_pk = self.request.POST.get('draft_id') or self.request.GET.get('draft')
        if draft_pk and not draft:
            draft = AdminEmailQueue.objects.filter(
                pk=draft_pk, status=AdminEmailStatus.DRAFT
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
            mail.save()
        else:
            mail = AdminEmailQueue.objects.create(
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

        _save_filters(mail, filters)

        if not is_draft:
            resolved = resolve_admin_recipients(filters)
            count = _populate_recipients(mail, resolved)

            import json
            from django.contrib.contenttypes.models import ContentType
            LogEntry.objects.create(
                content_type=ContentType.objects.get_for_model(AdminEmailQueue),
                object_id=mail.pk,
                user=self.request.user,
                action_type='eventyay.admin.mail.queued',
                data=json.dumps({
                    'admin_email_id': mail.pk,
                    'recipient_count': count,
                    'subject': mail.subject,
                }),
            )

            send_immediately = cd.get('send_immediately', False)
            if send_immediately:
                from eventyay.control.tasks import send_admin_email
                send_admin_email.apply_async(args=[mail.pk])
                messages.success(self.request, _('Your email is being sent to {count} recipients.').format(count=count))
            elif mail.scheduled_at:
                from eventyay.control.tasks import send_admin_email
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

        messages.success(self.request, _('The draft has been saved.'))
        return redirect('eventyay_admin:admin.messages.drafts')

    def _send_test_email(self, form, test_email: str):
        """Send a test email to the specified address."""
        from eventyay.common.mail import mail_send_task

        cd = form.cleaned_data
        subject = cd.get('subject', _('(No subject)'))
        body = cd.get('message', '')

        sample_context = {
            'user_name': 'Jane Doe',
            'first_name': 'Jane',
            'last_name': 'Doe',
            'email': test_email,
            'account_url': '',
            'platform_name': 'Eventyay',
            'platform_url': '',
            'support_email': 'support@eventyay.com',
            'support_url': '',
        }
        for key, value in sample_context.items():
            subject = subject.replace('{' + key + '}', value)
            body = body.replace('{' + key + '}', value)

        try:
            mail_send_task.apply_async(
                kwargs={
                    'to': [test_email],
                    'subject': f'[TEST] {subject}',
                    'body': body,
                    'html': AdminEmailQueue._make_html(None, body),
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
        """Build an email preview with sample placeholder values."""
        subject = cd.get('subject', '')
        body = cd.get('message', '')
        sample = {
            'user_name': 'Jane Doe',
            'first_name': 'Jane',
            'last_name': 'Doe',
            'email': 'jane@example.com',
            'account_url': '#',
            'platform_name': 'Eventyay',
            'platform_url': '#',
            'support_email': 'support@eventyay.com',
            'support_url': '#',
        }
        for key, value in sample.items():
            subject = subject.replace('{' + key + '}', value)
            body = body.replace('{' + key + '}', value)

        return {
            'subject': subject,
            'html': AdminEmailQueue._make_html(None, body),
        }


class AdminMessageOutboxView(AdministratorPermissionRequiredMixin, PaginationMixin, ListView):
    """List queued (unsent) admin emails."""

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
    """List draft admin emails."""

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
    """List sent admin emails."""

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
    """Read-only list of platform email templates."""

    template_name = 'pretixcontrol/admin/messages/templates.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['templates'] = self._get_platform_templates()
        return ctx

    def _get_platform_templates(self) -> list[dict]:
        """Collect all known platform email templates from MailTemplate roles."""
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
            {'name': _('Organiser invitation'), 'category': _('Team'), 'trigger': _('Team invitation sent')},
            {'name': _('Event team invitation'), 'category': _('Team'), 'trigger': _('Event team invitation sent')},
            {'name': _('Ticket order confirmation'), 'category': _('Ticketing'), 'trigger': _('Order placed')},
            {'name': _('Ticket cancellation'), 'category': _('Ticketing'), 'trigger': _('Order cancelled')},
            {'name': _('Refund notification'), 'category': _('Ticketing'), 'trigger': _('Refund processed')},
            {'name': _('CfP submission confirmation'), 'category': _('CfP'), 'trigger': _('Proposal submitted')},
            {'name': _('Proposal acceptance'), 'category': _('CfP'), 'trigger': _('Proposal accepted')},
            {'name': _('Proposal rejection'), 'category': _('CfP'), 'trigger': _('Proposal rejected')},
            {'name': _('Speaker schedule update'), 'category': _('Schedule'), 'trigger': _('Schedule updated')},
        ]
        for t in system_templates:
            t.setdefault('recipient_type', _('User'))
            t.setdefault('role', '')
        templates.extend(system_templates)

        return templates


class AdminMessageTemplateDetailView(AdministratorPermissionRequiredMixin, TemplateView):
    """Read-only detail view for a platform email template."""

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


# --- Action views ---

class AdminMessageSendView(AdministratorPermissionRequiredMixin, View):
    """Send a queued admin email immediately."""

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
    """Cancel a queued admin email."""

    def post(self, request, pk):
        mail = get_object_or_404(AdminEmailQueue, pk=pk, status=AdminEmailStatus.QUEUED)
        mail.status = AdminEmailStatus.CANCELLED
        mail.save(update_fields=['status'])
        messages.success(request, _('The email has been cancelled.'))
        return redirect('eventyay_admin:admin.messages.outbox')


class AdminMessageDeleteView(AdministratorPermissionRequiredMixin, View):
    """Delete a draft admin email."""

    def post(self, request, pk):
        mail = get_object_or_404(AdminEmailQueue, pk=pk, status=AdminEmailStatus.DRAFT)
        mail.delete()
        messages.success(request, _('The draft has been deleted.'))
        return redirect('eventyay_admin:admin.messages.drafts')


class AdminMessageDuplicateView(AdministratorPermissionRequiredMixin, View):
    """Duplicate an admin email as a new draft."""

    def post(self, request, pk):
        mail = get_object_or_404(AdminEmailQueue, pk=pk)
        new_mail = mail.duplicate()
        messages.success(request, _('The email has been duplicated as a draft.'))
        return redirect(new_mail.get_edit_url())


class AdminMessageRecipientsView(AdministratorPermissionRequiredMixin, View):
    """
    AJAX endpoint: returns recipient count and optional preview list.

    Accepts GET params matching the filter fields.
    """

    def get(self, request):
        form = AdminComposeRecipientsForm(data=request.GET)
        if not form.is_valid():
            return JsonResponse({'count': 0, 'recipients': [], 'errors': form.errors}, status=400)

        filters = _extract_filter_dict(form.cleaned_data)
        recipients = resolve_admin_recipients(filters)

        show_list = request.GET.get('show_list', '').lower() in ('1', 'true', 'yes')
        preview = []
        if show_list:
            for r in recipients[:100]:  # Limit preview to 100
                preview.append({
                    'name': r['name'],
                    'email': r['email'],
                    'status': r.get('status', ''),
                    'role': r.get('role', ''),
                    'reason': r.get('reason', ''),
                })

        skipped = sum(1 for r in recipients if not r.get('email'))
        return JsonResponse({
            'count': len(recipients),
            'skipped': skipped,
            'recipients': preview,
        })
