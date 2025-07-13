import logging
import uuid
import dateutil.parser

from django.db.models import Q

from pretix.base.models import CachedFile
from pretix.base.models.event import SubEvent

from .models import QueuedMail


logger = logging.getLogger('pretix.plugins.sendmail')


class CopyDraftMixin:
    def load_copy_draft(self, request, form_kwargs, team_mode=False):
        if copy_id := request.GET.get('copyToDraft'):
            try:
                mail_id = int(copy_id)
                qm = QueuedMail.objects.get(id=mail_id, event=request.event)
                form_kwargs['initial'] = form_kwargs.get('initial', {})

                subject = qm.raw_subject._data if hasattr(qm.raw_subject, '_data') else {'en': str(qm.raw_subject)}
                message = qm.raw_message._data if hasattr(qm.raw_message, '_data') else {'en': str(qm.raw_message)}

                attachments_qs = CachedFile.objects.filter(
                    id__in=[uuid.UUID(att_id) for att_id in qm.attachments]
                )
                attachment = attachments_qs.first() if attachments_qs.exists() else None

                filters = qm.filters or {}

                form_kwargs['initial'].update({
                    'subject': subject,
                    'message': message,
                    'reply_to': qm.reply_to,
                    'bcc': qm.bcc,
                })

                if attachment:
                    form_kwargs['initial']['attachment'] = attachment

                if team_mode:
                    form_kwargs['initial']['teams'] = filters.get('teams', [])
                else:
                    form_kwargs['initial'].update({
                        'recipients': filters.get('recipients', []),
                        'sendto': filters.get('sendto', ['p', 'na']),
                        'filter_checkins': filters.get('filter_checkins', False),
                        'not_checked_in': filters.get('not_checked_in', False),
                    })

                    if filters.get('items'):
                        form_kwargs['initial']['items'] = request.event.items.filter(
                            id__in=filters['items']
                        )
                    if filters.get('checkin_lists'):
                        form_kwargs['initial']['checkin_lists'] = request.event.checkin_lists.filter(
                            id__in=filters['checkin_lists']
                        )
                    if filters.get('subevent'):
                        try:
                            form_kwargs['initial']['subevent'] = request.event.subevents.get(
                                id=filters['subevent']
                            )
                        except SubEvent.DoesNotExist:
                            pass

                    date_fields = ['subevents_from', 'subevents_to', 'created_from', 'created_to']
                    for field in date_fields:
                        if filters.get(field):
                            form_kwargs['initial'][field] = dateutil.parser.isoparse(filters[field])
            except (QueuedMail.DoesNotExist, ValueError, TypeError) as e:
                logger.warning('Failed to load QueuedMail for copyToDraft: %s' % e)


class QueryFilterOrderingMixin:
    ordering_map = {
        'subject': 'raw_subject',
        'recipient': 'to_users',
        '-subject': '-raw_subject',
        '-recipient': '-to_users',
        'created': 'created_at',
        '-created': '-created_at'
    }

    def get_ordering(self):
        return self.ordering_map.get(self.request.GET.get('ordering'), '-created_at')

    def get_filtered_queryset(self, base_qs):
        if query := self.request.GET.get('q'):
            base_qs = base_qs.filter(
                Q(raw_subject__icontains=query) |
                Q(to_users__icontains=query)
            )
        return base_qs.order_by(self.get_ordering())
