import logging
import uuid
import dateutil.parser

from django.db.models import Q

from pretix.base.models import CachedFile
from pretix.base.models.event import SubEvent

from .models import QueuedMail, QueuedMailFilter


logger = logging.getLogger('pretix.plugins.sendmail')


class CopyDraftMixin:
    """
    Mixin to load a queued mail as an initial draft in a compose form via ?copyToDraft=<id>
    Supports both team and attendee email composition modes.
    """
    def load_copy_draft(self, request, form_kwargs, team_mode=False):
        if copy_id := request.GET.get('copyToDraft'):
            try:
                mail_id = int(copy_id)
                qm = QueuedMail.objects.get(id=mail_id, event=request.event)
                form_kwargs['initial'] = form_kwargs.get('initial', {})

                subject = qm.subject
                message = qm.message

                attachment = CachedFile.objects.filter(id__in=qm.attachments).first()

                try:
                    qmf = QueuedMailFilter.objects.get(mail=qm)
                except QueuedMailFilter.DoesNotExist:
                    qmf = None

                form_kwargs['initial'].update({
                    'subject': subject,
                    'message': message,
                    'reply_to': qm.reply_to,
                    'bcc': qm.bcc,
                })

                if attachment:
                    form_kwargs['initial']['attachment'] = attachment

                if qmf:
                    if team_mode:
                        form_kwargs['initial']['teams'] = qmf.teams or []
                    else:
                        form_kwargs['initial'].update({
                            'recipients': qmf.recipients or [],
                            'sendto': qmf.sendto or ['p', 'na'],
                            'filter_checkins': qmf.filter_checkins,
                            'not_checked_in': qmf.not_checked_in,
                        })

                        if qmf.items:
                            form_kwargs['initial']['items'] = request.event.items.filter(id__in=qmf.items)

                        if qmf.checkin_lists:
                            form_kwargs['initial']['checkin_lists'] = request.event.checkin_lists.filter(
                                id__in=qmf.checkin_lists
                            )

                        if qmf.subevent:
                            try:
                                form_kwargs['initial']['subevent'] = request.event.subevents.get(id=qmf.subevent)
                            except SubEvent.DoesNotExist:
                                pass

                        for field in ['subevents_from', 'subevents_to', 'created_from', 'created_to']:
                            value = getattr(qmf, field, None)
                            if value:
                                form_kwargs['initial'][field] = dateutil.parser.isoparse(value) if isinstance(value, str) else value

            except (QueuedMail.DoesNotExist, ValueError, TypeError) as e:
                logger.warning('Failed to load QueuedMail for copyToDraft: %s' % e)


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
