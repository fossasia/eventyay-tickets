import logging
import dateutil.parser

from django.contrib import messages
from django.db.models import Exists, OuterRef, Q
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import CachedFile, Order, OrderPosition, Team
from eventyay.base.models.event import SubEvent

from .models import ComposingFor, EmailQueue, EmailQueueFilter


logger = logging.getLogger(__name__)


def ensure_draft_defaults(data):
    data = data.copy()
    if not any(value.strip() for key, value in data.items() if key.startswith('subject_')):
        data['subject_0'] = _('Untitled draft')
    if not any(value.strip() for key, value in data.items() if key.startswith('text_') or key.startswith('message_')):
        data['text_0'] = ' '
        data['message_0'] = ' '
    return data


def calculate_attendee_recipient_count(event, qmf):
    if not qmf:
        return 0

    if qmf.recipients == 'individual':
        if not qmf.individual_attendees:
            return 0
        positions = OrderPosition.objects.filter(
            order__event=event,
            pk__in=qmf.individual_attendees,
            canceled=False,
        ).select_related('order')
        unique_emails = {pos.attendee_email.strip().lower() for pos in positions if pos.attendee_email}
        return len(unique_emails)

    orders = Order.objects.filter(event=event)
    order_statuses = qmf.order_status
    statusq = Q(status__in=order_statuses)
    if 'overdue' in order_statuses:
        statusq |= Q(status=Order.STATUS_PENDING, expires__lt=now())
    if 'pa' in order_statuses:
        statusq |= Q(status=Order.STATUS_PENDING, require_approval=True)
    if 'na' in order_statuses:
        statusq |= Q(status=Order.STATUS_PENDING, require_approval=False)
    orders = orders.filter(statusq)

    opq = OrderPosition.objects.filter(
        order=OuterRef('pk'),
        canceled=False,
    )
    if qmf.products:
        opq = opq.filter(product_id__in=qmf.products)

    if qmf.has_filter_checkins:
        ql = []
        if qmf.not_checked_in:
            ql.append(Q(checkins__list_id=None))
        if qmf.checkin_lists:
            ql.append(Q(checkins__list_id__in=qmf.checkin_lists))
        if len(ql) == 2:
            opq = opq.filter(ql[0] | ql[1])
        elif ql:
            opq = opq.filter(ql[0])
        else:
            opq = opq.none()

    if qmf.subevent:
        opq = opq.filter(subevent_id=qmf.subevent)
    if qmf.subevents_from:
        opq = opq.filter(subevent__date_from__gte=qmf.subevents_from)
    if qmf.subevents_to:
        opq = opq.filter(subevent__date_from__lt=qmf.subevents_to)
    if qmf.order_created_from:
        opq = opq.filter(order__datetime__gte=qmf.order_created_from)
    if qmf.order_created_to:
        opq = opq.filter(order__datetime__lt=qmf.order_created_to)

    orders = orders.annotate(match_pos=Exists(opq)).filter(match_pos=True).distinct()

    recipients_mode = qmf.recipients or "orders"
    unique_emails = set()
    for order in orders.prefetch_related('positions__product'):
        order_fallback_needed = False
        attendee_found = False
        for pos in order.positions.all():
            if pos.attendee_email:
                attendee_found = True
                unique_emails.add(pos.attendee_email.strip().lower())
            else:
                order_fallback_needed = True

        if order_fallback_needed and not attendee_found and recipients_mode == "attendees" and order.email:
            unique_emails.add(order.email.strip().lower())
        if recipients_mode in ("both", "orders") and order.email:
            unique_emails.add(order.email.strip().lower())

    return len(unique_emails)


def calculate_team_recipient_count(event, qmf, user=None):
    if not qmf:
        return 0
    from eventyay.base.models import User

    team_filters = {'teams__organizer': event.organizer}
    if qmf.teams:
        team_filters['teams__in'] = qmf.teams
    if qmf.team_role:
        team_filters['teams__teamshifts_role'] = qmf.team_role
    if qmf.permission_level:
        team_filters[f'teams__{qmf.permission_level}'] = True

    qs = User.objects.filter(**team_filters)
    if qmf.status == 'active':
        qs = qs.filter(is_active=True)
    elif qmf.status == 'inactive':
        qs = qs.filter(is_active=False)
    if qmf.specific_people:
        qs = qs.filter(pk__in=qmf.specific_people)
    if qmf.exclude_me and user:
        qs = qs.exclude(pk=user.pk)

    return qs.filter(email__isnull=False).exclude(email='').distinct().count()


class CopyDraftMixin:
    """
    Mixin to load a queued mail as an initial draft in a compose form via ?draft=<id> or ?copyToDraft=<id>.
    Supports both team and attendee email composition modes.
    """
    def load_copy_draft(self, request, form_kwargs, team_mode=False):
        draft_id = request.GET.get('draft')
        copy_id = request.GET.get('copyToDraft')
        target_id = draft_id or copy_id

        if post_draft_id := request.POST.get('draft_id'):
            try:
                self.draft_id = int(post_draft_id)
            except (ValueError, TypeError):
                pass

        if target_id:
            try:
                mail_id = int(target_id)
                qm = EmailQueue.objects.get(
                    id=mail_id,
                    event=request.event,
                    composing_for=ComposingFor.TEAMS if team_mode else ComposingFor.ATTENDEES,
                    is_draft=bool(draft_id),
                )
                form_kwargs['initial'] = form_kwargs.get('initial', {})

                subject = qm.subject
                message = qm.message
                attachment = (
                    CachedFile.objects.filter(id__in=qm.attachments).first()
                    if qm.attachments
                    else None
                )

                try:
                    qmf = EmailQueueFilter.objects.get(mail=qm)
                except EmailQueueFilter.DoesNotExist:
                    qmf = None

                body_field = 'message' if team_mode else 'text'
                form_kwargs['initial'].update({
                    'subject': subject,
                    body_field: message,
                    'reply_to': qm.reply_to,
                    'bcc': qm.bcc,
                    'scheduled_at': qm.scheduled_at,
                })

                if attachment:
                    form_kwargs['initial']['attachment'] = attachment

                if qmf:
                    if team_mode:
                        form_kwargs['initial'].update({
                            'teams': qmf.teams or [],
                            'team_role': qmf.team_role or '',
                            'permission_level': qmf.permission_level or '',
                            'status': qmf.status or '',
                            'specific_people': qmf.specific_people or [],
                            'exclude_me': qmf.exclude_me,
                        })
                    else:
                        form_kwargs['initial'].update({
                            'recipients': qmf.recipients or 'orders',
                            'order_status': qmf.order_status or ['p', 'na'],
                            'has_filter_checkins': qmf.has_filter_checkins,
                            'not_checked_in': qmf.not_checked_in,
                        })

                        if qmf.products:
                            form_kwargs['initial']['products'] = request.event.products.filter(id__in=qmf.products)

                        if qmf.checkin_lists:
                            form_kwargs['initial']['checkin_lists'] = request.event.checkin_lists.filter(
                                id__in=qmf.checkin_lists
                            )

                        if qmf.subevent:
                            try:
                                form_kwargs['initial']['subevent'] = request.event.subevents.get(id=qmf.subevent)
                            except SubEvent.DoesNotExist:
                                pass

                        if qmf.individual_attendees:
                            form_kwargs['initial']['individual_attendees'] = OrderPosition.objects.filter(
                                id__in=qmf.individual_attendees
                            )

                        for field in ['subevents_from', 'subevents_to', 'order_created_from', 'order_created_to']:
                            value = getattr(qmf, field, None)
                            if value:
                                form_kwargs['initial'][field] = dateutil.parser.isoparse(value) if isinstance(value, str) else value

                if draft_id:
                    self.draft_id = qm.pk
                    self.loaded_draft = qm
                    old_count = qm.recipients.count() if hasattr(qm.recipients, 'count') else len(qm.recipients or [])
                    if team_mode:
                        new_count = calculate_team_recipient_count(request.event, qmf, user=request.user)
                    else:
                        new_count = calculate_attendee_recipient_count(request.event, qmf)

                    self.recipient_count = new_count
                    if request.method == 'GET' and old_count != new_count:
                        messages.info(
                            request,
                            _('Recipient count changed from {old_count} to {new_count} because event data changed since this draft was saved.').format(
                                old_count=old_count,
                                new_count=new_count,
                            )
                        )
                elif copy_id:
                    if team_mode:
                        self.recipient_count = calculate_team_recipient_count(request.event, qmf, user=request.user)
                    else:
                        self.recipient_count = calculate_attendee_recipient_count(request.event, qmf)

            except (EmailQueue.DoesNotExist, ValueError, TypeError) as e:
                logger.warning('Failed to load EmailQueue for draft/copyToDraft: %s', e)


class QueryFilterOrderingMixin:
    """
    Mixin to provide search and dynamic ordering to list views using ?q= and ?ordering=
    """
    ordering_map = {
    'subject': 'subject',
    'recipient': 'first_recipient_email',
    '-subject': '-subject',
    '-recipient': '-first_recipient_email',
    'created': 'sent_at',
    '-created': '-sent_at',
    }

    def get_ordering(self):
        return self.ordering_map.get(self.request.GET.get('ordering'), '-sent_at')

    def get_filtered_queryset(self, base_qs):
        if query := self.request.GET.get('q'):
            base_qs = base_qs.filter(
                Q(subject__icontains=query) |
                Q(recipients__email__icontains=query)
            ).distinct()
        return base_qs.order_by(self.get_ordering())
