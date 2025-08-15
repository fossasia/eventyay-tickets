import operator
from functools import reduce

import django_filters
from django.conf import settings
from django.core.exceptions import ValidationError as BaseValidationError
from django.db.models import (
    Count,
    Exists,
    F,
    Max,
    OrderBy,
    OuterRef,
    Prefetch,
    Q,
    Subquery,
    prefetch_related_objects,
)
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property
from django.utils.timezone import now
from django_filters.rest_framework import DjangoFilterBackend, FilterSet
from django_scopes import scopes_disabled
from rest_framework import status, views, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.fields import DateTimeField
from rest_framework.generics import ListAPIView
from rest_framework.response import Response

from pretix.api.serializers.checkin import (
    CheckinListSerializer,
    CheckinRedeemInputSerializer,
    MiniCheckinListSerializer,
)
from pretix.api.serializers.item import QuestionSerializer
from pretix.api.serializers.order import CheckinListOrderPositionSerializer
from pretix.api.views import RichOrderingFilter
from pretix.api.views.order import OrderPositionFilter
from pretix.base.i18n import language
from pretix.base.models import (
    CachedFile,
    Checkin,
    CheckinList,
    Device,
    Event,
    Room,
    Order,
    OrderPosition,
    Question,
    RevokedTicketSecret,
    TeamAPIToken,
)
from pretix.base.services.checkin import (
    CheckInError,
    RequiredQuestionsError,
    SQLLogic,
    perform_checkin,
)
from pretix.base.services.tasks import ProfiledEventTask
from pretix.celery_app import app
from pretix.helpers.database import FixedOrderBy


@app.task(base=ProfiledEventTask, bind=True)
def bulk_checkout_task(self, event_id, user_id=None, auth_id=None, auth_type=None):
    """
    Background task to perform bulk checkout for all attendees in an event.
    """
    from django.utils.timezone import now
    from pretix.base.models import Event, User, TeamAPIToken, Device
    
    with scopes_disabled():
        event = Event.objects.get(pk=event_id)
        user = User.objects.get(pk=user_id) if user_id else None
        
        # Reconstruct auth object if needed
        auth = None
        if auth_type == 'TeamAPIToken' and auth_id:
            auth = TeamAPIToken.objects.get(pk=auth_id)
        elif auth_type == 'Device' and auth_id:
            auth = Device.objects.get(pk=auth_id)
    
    # Get all checkin lists for this event
    checkin_lists = event.checkin_lists.all()
    
    if not checkin_lists.exists():
        return {
            'status': 'error',
            'message': 'No check-in lists found for this event.',
            'checkout_count': 0,
            'errors': []
        }

    checkout_count = 0
    errors = []

    # Process checkout for each checkin list
    for clist in checkin_lists:
        try:
            # Get all currently checked-in positions for this list
            checked_in_positions = clist.positions_inside
            
            for position in checked_in_positions:
                try:
                    # Use the proper checkin service for consistency
                    perform_checkin(
                        op=position,
                        clist=clist,
                        given_answers={},
                        force=True,
                        ignore_unpaid=True,
                        datetime=now(),
                        questions_supported=False,
                        user=user,
                        auth=auth,
                        type=Checkin.TYPE_EXIT,
                    )
                    checkout_count += 1
                    
                except (CheckInError, RequiredQuestionsError) as e:
                    errors.append({
                        'position_id': position.id,
                        'order_code': position.order.code,
                        'error': str(e)
                    })
                except Exception as e:
                    errors.append({
                        'position_id': position.id,
                        'order_code': position.order.code,
                        'error': f'Unexpected error: {str(e)}'
                    })
                    
        except Exception as e:
            errors.append({
                'checkin_list': clist.name,
                'error': f'List processing error: {str(e)}'
            })

    # Log the event-wide checkout action
    event.log_action(
        'pretix.event.checkout_all',
        data={
            'checkout_count': checkout_count,
            'errors_count': len(errors),
            'datetime': now().isoformat(),
        },
        user=user,
        auth=auth,
    )

    return {
        'status': 'partial_success' if errors else 'success',
        'checkout_count': checkout_count,
        'errors': errors,
        'message': f'Successfully checked out {checkout_count} attendees.'
    }


with scopes_disabled():

    class CheckinListFilter(FilterSet):
        subevent_match = django_filters.NumberFilter(method='subevent_match_qs')
        ends_after = django_filters.rest_framework.IsoDateTimeFilter(method='ends_after_qs')

        class Meta:
            model = CheckinList
            fields = ['subevent']

        def subevent_match_qs(self, qs, name, value):
            return qs.filter(Q(subevent_id=value) | Q(subevent_id__isnull=True))

        def ends_after_qs(self, queryset, name, value):
            expr = Q(subevent__isnull=True) | Q(
                Q(Q(subevent__date_to__isnull=True) & Q(subevent__date_from__gte=value))
                | Q(Q(subevent__date_to__isnull=False) & Q(subevent__date_to__gte=value))
            )
            return queryset.filter(expr)


class CheckinListViewSet(viewsets.ModelViewSet):
    serializer_class = CheckinListSerializer
    queryset = CheckinList.objects.none()
    filter_backends = (DjangoFilterBackend,)
    filterset_class = CheckinListFilter
    permission = (
        'can_view_orders',
        'can_checkin_orders',
    )
    write_permission = 'can_change_event_settings'

    def get_queryset(self):
        qs = self.request.event.checkin_lists.prefetch_related(
            'limit_products',
        )

        if 'subevent' in self.request.query_params.getlist('expand'):
            qs = qs.prefetch_related(
                'subevent',
                'subevent__event',
                'subevent__subeventitem_set',
                'subevent__subeventitemvariation_set',
                'subevent__seat_category_mappings',
                'subevent__meta_values',
            )
        return qs

    def perform_create(self, serializer):
        serializer.save(event=self.request.event)
        serializer.instance.log_action(
            'pretix.event.checkinlist.added',
            user=self.request.user,
            auth=self.request.auth,
            data=self.request.data,
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['event'] = self.request.event
        return ctx

    def perform_update(self, serializer):
        serializer.save(event=self.request.event)
        serializer.instance.log_action(
            'pretix.event.checkinlist.changed',
            user=self.request.user,
            auth=self.request.auth,
            data=self.request.data,
        )

    def perform_destroy(self, instance):
        instance.log_action(
            'pretix.event.checkinlist.deleted',
            user=self.request.user,
            auth=self.request.auth,
        )
        super().perform_destroy(instance)

    @action(detail=True, methods=['GET'])
    def status(self, *args, **kwargs):
        with language(self.request.event.settings.locale):
            clist = self.get_object()
            cqs = clist.positions.annotate(
                checkedin=Exists(
                    Checkin.objects.filter(
                        list_id=clist.pk,
                        position=OuterRef('pk'),
                        type=Checkin.TYPE_ENTRY,
                    )
                )
            ).filter(
                checkedin=True,
            )
            pqs = clist.positions

            ev = clist.subevent or clist.event
            # Optional per-day filter and available dates for UI
            selected_date = None
            entry_count_on_date = None
            exit_count_on_date = None
            available_dates = []
            try:
                from django.utils.dateparse import parse_date
                # Build available dates from the event/subevent date range
                ev_start = (ev.date_admission or ev.date_from).date()
                ev_end = (ev.date_to or ev.date_from).date()
                if ev_start and ev_end:
                    from datetime import timedelta
                    d = ev_start
                    while d <= ev_end:
                        available_dates.append(d.isoformat())
                        d += timedelta(days=1)
                # Parse requested date
                if 'date' in self.request.query_params:
                    parsed = parse_date(self.request.query_params.get('date'))
                    if parsed and parsed.isoformat() in available_dates:
                        selected_date = parsed
            except Exception:
                pass

            if selected_date:
                entry_count_on_date = Checkin.objects.filter(
                    list_id=clist.pk,
                    type=Checkin.TYPE_ENTRY,
                    datetime__date=selected_date,
                ).count()
                exit_count_on_date = Checkin.objects.filter(
                    list_id=clist.pk,
                    type=Checkin.TYPE_EXIT,
                    datetime__date=selected_date,
                ).count()
            response = {
                'event': {
                    'name': str(ev.name),
                },
                'checkin_count': cqs.count(),
                'position_count': pqs.count(),
                'inside_count': clist.inside_count,
                'available_dates': available_dates,
                'selected_date': selected_date.isoformat() if selected_date else None,
                'entry_count_on_date': entry_count_on_date,
                'exit_count_on_date': exit_count_on_date,
            }

            op_by_item = {p['item']: p['cnt'] for p in pqs.order_by().values('item').annotate(cnt=Count('id'))}
            op_by_variation = {
                p['variation']: p['cnt'] for p in pqs.order_by().values('variation').annotate(cnt=Count('id'))
            }
            c_by_item = {p['item']: p['cnt'] for p in cqs.order_by().values('item').annotate(cnt=Count('id'))}
            c_by_variation = {
                p['variation']: p['cnt'] for p in cqs.order_by().values('variation').annotate(cnt=Count('id'))
            }

            if not clist.all_products:
                items = clist.limit_products
            else:
                items = clist.event.items

            response['items'] = []
            for item in items.order_by('category__position', 'position', 'pk').prefetch_related('variations'):
                i = {
                    'id': item.pk,
                    'name': str(item),
                    'admission': item.admission,
                    'checkin_count': c_by_item.get(item.pk, 0),
                    'position_count': op_by_item.get(item.pk, 0),
                    'variations': [],
                }
                for var in item.variations.all():
                    i['variations'].append(
                        {
                            'id': var.pk,
                            'value': str(var),
                            'checkin_count': c_by_variation.get(var.pk, 0),
                            'position_count': op_by_variation.get(var.pk, 0),
                        }
                    )
                response['items'].append(i)

            return Response(response)


with scopes_disabled():

    class CheckinOrderPositionFilter(OrderPositionFilter):
        check_rules = django_filters.rest_framework.BooleanFilter(method='check_rules_qs')
        # check_rules is currently undocumented on purpose, let's get a feel for the performance impact first

        def __init__(self, *args, **kwargs):
            self.checkinlist = kwargs.pop('checkinlist')
            super().__init__(*args, **kwargs)

        def has_checkin_qs(self, queryset, name, value):
            return queryset.filter(last_checked_in__isnull=not value)

        def check_rules_qs(self, queryset, name, value):
            if not self.checkinlist.rules:
                return queryset
            return queryset.filter(SQLLogic(self.checkinlist).apply(self.checkinlist.rules))


def _checkin_list_position_queryset(
    checkinlists,
    ignore_status=False,
    ignore_products=False,
    pdf_data=False,
    expand=None,
):
    list_by_event = {cl.event_id: cl for cl in checkinlists}
    if not checkinlists:
        raise BaseValidationError('No check-in list passed.')
    # Allow multiple check-in lists from the same event for multi-day events
    # if len(list_by_event) != len(checkinlists):
    #     raise BaseValidationError('Selecting two check-in lists from the same event is unsupported.')

    cqs = (
        Checkin.objects.filter(position_id=OuterRef('pk'), list_id__in=[cl.pk for cl in checkinlists])
        .order_by()
        .values('position_id')
        .annotate(m=Max('datetime'))
        .values('m')
    )

    qs = (
        OrderPosition.objects.filter(
            order__event__in=list_by_event.keys(),
        )
        .annotate(last_checked_in=Subquery(cqs))
        .prefetch_related('order__event', 'order__event__organizer')
    )

    lists_qs = []
    for checkinlist in checkinlists:
        list_q = Q(order__event_id=checkinlist.event_id)
        if checkinlist.subevent:
            list_q &= Q(subevent=checkinlist.subevent)
        if not ignore_status:
            if checkinlist.include_pending:
                list_q &= Q(order__status__in=[Order.STATUS_PAID, Order.STATUS_PENDING])
            else:
                list_q &= Q(
                    Q(order__status=Order.STATUS_PAID)
                    | Q(order__status=Order.STATUS_PENDING, order__valid_if_pending=True)
                )
        if not checkinlist.all_products and not ignore_products:
            list_q &= Q(item__in=checkinlist.limit_products.values_list('id', flat=True))
        lists_qs.append(list_q)

    qs = qs.filter(reduce(operator.or_, lists_qs))

    if pdf_data:
        qs = qs.prefetch_related(
            Prefetch(
                lookup='checkins',
                queryset=Checkin.objects.filter(list_id__in=[cl.pk for cl in checkinlists]),
            ),
            'answers',
            'answers__options',
            'answers__question',
            Prefetch('addons', OrderPosition.objects.select_related('item', 'variation')),
            Prefetch(
                'order',
                Order.objects.select_related('invoice_address').prefetch_related(
                    Prefetch('event', Event.objects.select_related('organizer')),
                    Prefetch(
                        'positions',
                        OrderPosition.objects.prefetch_related(
                            Prefetch('checkins', queryset=Checkin.objects.all()),
                            'item',
                            'variation',
                            'answers',
                            'answers__options',
                            'answers__question',
                        ),
                    ),
                ),
            ),
        ).select_related(
            'item',
            'variation',
            'item__category',
            'addon_to',
            'order',
            'order__invoice_address',
            'seat',
        )
    else:
        qs = qs.prefetch_related(
            Prefetch(
                lookup='checkins',
                queryset=Checkin.objects.filter(list_id__in=[cl.pk for cl in checkinlists]),
            ),
            'answers',
            'answers__options',
            'answers__question',
            Prefetch('addons', OrderPosition.objects.select_related('item', 'variation')),
        ).select_related(
            'item',
            'variation',
            'order',
            'addon_to',
            'order__invoice_address',
            'order',
            'seat',
        )

    if expand and 'subevent' in expand:
        qs = qs.prefetch_related(
            'subevent',
            'subevent__event',
            'subevent__subeventitem_set',
            'subevent__subeventitemvariation_set',
            'subevent__seat_category_mappings',
            'subevent__meta_values',
        )

    if expand and 'item' in expand:
        qs = qs.prefetch_related(
            'item',
            'item__addons',
            'item__bundles',
            'item__meta_values',
            'item__variations',
        ).select_related('item__tax_rule')

    if expand and 'variation' in expand:
        qs = qs.prefetch_related('variation', 'variation__meta_values')

    return qs


def _handle_file_upload(data, user, auth):
    try:
        cf = CachedFile.objects.get(
            session_key=f'api-upload-{str(type(user or auth))}-{(user or auth).pk}',
            file__isnull=False,
            pk=data[len('file:') :],
        )
    except (BaseValidationError, IndexError):  # invalid uuid
        raise BaseValidationError('The submitted file ID "{fid}" was not found.'.format(fid=data))
    except CachedFile.DoesNotExist:
        raise BaseValidationError('The submitted file ID "{fid}" was not found.'.format(fid=data))

    allowed_types = ('image/png', 'image/jpeg', 'image/gif', 'application/pdf')
    if cf.type not in allowed_types:
        raise BaseValidationError(
            'The submitted file "{fid}" has a file type that is not allowed in this field.'.format(fid=data)
        )
    if cf.file.size > settings.FILE_UPLOAD_MAX_SIZE_OTHER:
        raise BaseValidationError('The submitted file "{fid}" is too large to be used in this field.'.format(fid=data))

    return cf.file


def _validate_checkinlists(checkinlists):
    if not checkinlists:
        raise BaseValidationError('No check-in list passed.')

    list_by_event = {checkinlist.event_id: checkinlist for checkinlist in checkinlists}
    prefetch_related_objects(
        [checkinlist for checkinlist in checkinlists if not checkinlist.all_products],
        'limit_products',
    )
    return list_by_event


def _setup_context(request, expand, event=None, pdf_data=None, user=None, auth=None):
    base_context = {
        'request': request,
        'expand': expand,
    }

    if event:
        return {
            **base_context,
            'event': event,
            'pdf_data': pdf_data
            and (user if user and user.is_authenticated else auth).has_event_permission(
                request.organizer, event, 'can_view_orders', request
            ),
        }
    return base_context


def _get_common_checkin_args(checkinlists, checkin_type, dateandtime, device, gate, nonce, force, simulate=False):
    args = {
        'type': checkin_type,
        'list': checkinlists[0],
        'datetime': dateandtime,
        'device': device,
        'gate': gate,
        'nonce': nonce,
        'forced': force,
    }
    if simulate:
        args['__fake_arg_to_prevent_this_from_being_saved'] = True
    return args


def _build_search_query(raw_barcode, untrusted_input, legacy_url_support):
    q = Q(secret=raw_barcode)
    if raw_barcode.isnumeric() and not untrusted_input and legacy_url_support:
        q |= Q(pk=raw_barcode)
    return q


def _handle_no_candidates(
    checkinlists,
    raw_barcode,
    common_checkin_args,
    dateandtime,
    checkin_type,
    user,
    auth,
    simulate,
):
    checkinlists[0].event.log_action(
        'pretix.event.checkin.unknown',
        data={
            'datetime': dateandtime,
            'type': checkin_type,
            'list': checkinlists[0].pk,
            'barcode': raw_barcode,
            'searched_lists': [cl.pk for cl in checkinlists],
        },
        user=user,
        auth=auth,
    )

    for cl in checkinlists:
        for k, s in cl.event.ticket_secret_generators.items():
            try:
                parsed = s.parse_secret(raw_barcode)
                common_checkin_args.update(
                    {
                        'raw_item': parsed.item,
                        'raw_variation': parsed.variation,
                        'raw_subevent': parsed.subevent,
                    }
                )
            except:
                pass

    # Note: Cannot create Checkin record for invalid tickets as position is required
    # This is handled by the log_action call above
    return Response(
        {
            'detail': 'Not found.',
            'status': 'error',
            'reason': 'invalid',
            'reason_explanation': None,
            'require_attention': False,
            'checkin_texts': [],
            'list': MiniCheckinListSerializer(checkinlists[0]).data,
        },
        status=404,
    )


def _filter_matching_candidates(op_candidates, list_by_event, raw_barcode, legacy_url_support):
    return [
        op
        for op in op_candidates
        if (
            (list_by_event[op.order.event_id].addon_match or op.secret == raw_barcode or legacy_url_support)
            and (
                list_by_event[op.order.event_id].all_products
                or op.item_id in {i.pk for i in list_by_event[op.order.event_id].limit_products.all()}
            )
        )
    ]


def _handle_ambiguous_candidates(op, common_checkin_args, list_by_event, context, user, auth, simulate):
    if not simulate:
        op.order.log_action(
            'pretix.event.checkin.denied',
            data={
                'position': op.id,
                'positionid': op.positionid,
                'errorcode': 'ambiguous',
                'reason_explanation': None,
                'force': common_checkin_args['forced'],
                'datetime': common_checkin_args['datetime'],
                'type': common_checkin_args['type'],
                'list': list_by_event[op.order.event_id].pk,
            },
            user=user,
            auth=auth,
        )
        common_checkin_args['list'] = list_by_event[op.order.event_id]
        Checkin.objects.create(
            position=op,
            successful=False,
            error_reason='ambiguous',
            error_explanation=None,
            **common_checkin_args,
        )

    return Response(
        {
            'status': 'error',
            'reason': 'ambiguous',
            'reason_explanation': None,
            'require_attention': op.require_checkin_attention,
            'position': CheckinListOrderPositionSerializer(
                op, context=_setup_context(**context, event=op.order.event)
            ).data,
            'list': MiniCheckinListSerializer(list_by_event[op.order.event_id]).data,
        },
        status=400,
    )


def _process_given_answers(op, answers_data, user, auth):
    given_answers = {}
    if answers_data:
        for q in op.item.questions.filter(ask_during_checkin=True):
            if str(q.pk) in answers_data:
                try:
                    if q.type == Question.TYPE_FILE:
                        given_answers[q] = _handle_file_upload(answers_data[str(q.pk)], user, auth)
                    else:
                        given_answers[q] = q.clean_answer(answers_data[str(q.pk)])
                except BaseValidationError:
                    pass
    return given_answers


def _append_badge_download(downloads, op, request):
    if 'pretix.plugins.badges' in op.order.event.plugins:
        badge_url = f'/api/v1/organizers/{request.organizer.slug}/events/{op.order.event.slug}/orderpositions/{op.pk}/download/badge/'
        downloads.append({'output': 'badge', 'url': badge_url})
    return downloads


def _redeem_process(
    *,
    checkinlists,
    raw_barcode,
    answers_data,
    dateandtime,
    force,
    checkin_type,
    ignore_unpaid,
    nonce,
    untrusted_input,
    user,
    auth,
    expand,
    pdf_data,
    request,
    questions_supported,
    canceled_supported,
    source_type='barcode',
    legacy_url_support=False,
    simulate=False,
    gate=None,
):
    list_by_event = _validate_checkinlists(checkinlists)

    device = auth if isinstance(auth, Device) else None
    gate = gate or (auth.gate if isinstance(auth, Device) else None)
    context = _setup_context(request, expand)

    # Note: room active enforcement is applied per-event below once the target event is known

    # Simple gate-aware list selection without changing existing API contracts:
    # - If a device has a gate, prefer a provided check-in list that is associated with that gate for the event
    # - If no gate is present, prefer a provided check-in list without any gates (acting as a default list)
    # - Otherwise, fall back to the first provided list per event (existing behavior)
    if checkinlists:
        # Build a map of event -> all provided lists for that event
        candidates_by_event = {}
        for cl in checkinlists:
            candidates_by_event.setdefault(cl.event_id, []).append(cl)

        for ev_id, current_selected in list_by_event.items():
            candidates = candidates_by_event.get(ev_id, [])
            if not candidates:
                continue
            if gate:
                # Pick first candidate that is linked to the device's gate
                selected = None
                for cl in candidates:
                    if cl.gates.filter(pk=gate.pk).exists():
                        selected = cl
                        break
                if selected:
                    list_by_event[ev_id] = selected
            else:
                # No gate: prefer a candidate with no gates set (treat as default)
                selected = None
                for cl in candidates:
                    if cl.gates.count() == 0:
                        selected = cl
                        break
                if selected:
                    list_by_event[ev_id] = selected

    common_checkin_args = _get_common_checkin_args(
        checkinlists, checkin_type, dateandtime, device, gate, nonce, force, simulate
    )

    queryset = _checkin_list_position_queryset(
        checkinlists, pdf_data=pdf_data, ignore_status=True, ignore_products=True
    ).order_by(F('addon_to').asc(nulls_first=True))

    q = _build_search_query(raw_barcode, untrusted_input, legacy_url_support)
    op_candidates = list(queryset.filter(q))

    if not op_candidates:
        revoked = list(RevokedTicketSecret.objects.filter(event_id__in=list_by_event.keys(), secret=raw_barcode))
        if len(revoked) == 0:
            return _handle_no_candidates(
                checkinlists,
                raw_barcode,
                common_checkin_args,
                dateandtime,
                checkin_type,
                user,
                auth,
                simulate,
            )

    if len(op_candidates) > 1:
        op_candidates_matching_product = _filter_matching_candidates(
            op_candidates, list_by_event, raw_barcode, legacy_url_support
        )

        if len(op_candidates_matching_product) == 0:
            op_candidates = [op_candidates[0]]
        elif len(op_candidates_matching_product) > 1:
            return _handle_ambiguous_candidates(
                op_candidates[0],
                common_checkin_args,
                list_by_event,
                context,
                user,
                auth,
                simulate,
            )
        else:
            op_candidates = op_candidates_matching_product

    op = op_candidates[0]

    # Enforce room active state for the specific event tied to this scan
    if gate and checkin_type == Checkin.TYPE_ENTRY:
        gate_room = Room.objects.filter(event=op.order.event, gates=gate).first()
        if gate_room and not gate_room.is_active:
            return Response(
                {
                    'status': 'error',
                    'reason': 'room_inactive',
                    'reason_explanation': 'The room associated with this device gate is inactive.',
                    'gate': getattr(gate, 'pk', None),
                    'room': {
                        'id': gate_room.id,
                        'name': gate_room.name,
                        'is_active': gate_room.is_active,
                    },
                    'list': MiniCheckinListSerializer(checkinlists[0]).data if checkinlists else None,
                    'require_attention': False,
                    'checkin_texts': [],
                },
                status=400,
            )
    
    # Determine the appropriate CheckinList based on gate presence
    target_checkin_list = list_by_event[op.order.event_id]
    
    # If device has a gate, try to find gate-specific CheckinList
    if gate:
        from pretix.base.models import CheckinList
        gate_checkin_lists = CheckinList.objects.filter(
            event=op.order.event,
            gates=gate
        ).first()
        
        if gate_checkin_lists:
            target_checkin_list = gate_checkin_lists
            # Update list_by_event to include gate-specific list for consistency
            list_by_event[op.order.event_id] = target_checkin_list
    
    # Update common_checkin_args to use the correct CheckinList
    common_checkin_args['list'] = target_checkin_list
    given_answers = _process_given_answers(op, answers_data, user, auth)

    with language(op.order.event.settings.locale):
        try:
            perform_checkin(
                op=op,
                clist=target_checkin_list,
                given_answers=given_answers,
                force=force,
                ignore_unpaid=ignore_unpaid,
                nonce=nonce,
                datetime=dateandtime,
                questions_supported=questions_supported,
                canceled_supported=canceled_supported,
                user=user,
                auth=auth,
                type=checkin_type,
            )
        except RequiredQuestionsError as e:
            return Response(
                {
                    'status': 'incomplete',
                    'require_attention': op.require_checkin_attention,
                    'position': CheckinListOrderPositionSerializer(
                        op,
                        context=_setup_context(request, expand, op.order.event, pdf_data, user, auth),
                    ).data,
                    'questions': [QuestionSerializer(q).data for q in e.questions],
                    'list': MiniCheckinListSerializer(target_checkin_list).data,
                },
                status=400,
            )
        except CheckInError as e:
            if not simulate:
                op.order.log_action(
                    'pretix.event.checkin.denied',
                    data={
                        'position': op.id,
                        'positionid': op.positionid,
                        'errorcode': e.code,
                        'reason_explanation': 'unkown',
                        'force': force,
                        'datetime': dateandtime,
                        'type': checkin_type,
                        'list': target_checkin_list.pk,
                    },
                    user=user,
                    auth=auth,
                )
                Checkin.objects.create(
                    position=op,
                    **common_checkin_args,
                )

            serializer_context = _setup_context(request, expand, op.order.event, pdf_data, user, auth)
            position_data = CheckinListOrderPositionSerializer(op, context=serializer_context).data
            downloads = _append_badge_download(position_data['downloads'], op, request)
            position_data['downloads'] = downloads

            return Response(
                {
                    'status': 'redeemed',
                    'reason': 'Already checked in',
                    'require_attention': op.require_checkin_attention,
                    'position': position_data,
                    'list': MiniCheckinListSerializer(target_checkin_list).data,
                },
                status=201,
            )
        else:
            serializer_context = _setup_context(request, expand, op.order.event, pdf_data, user, auth)
            position_data = CheckinListOrderPositionSerializer(op, context=serializer_context).data
            downloads = _append_badge_download(position_data['downloads'], op, request)
            position_data['downloads'] = downloads

            return Response(
                {
                    'status': 'ok',
                    'require_attention': op.require_checkin_attention,
                    'position': position_data,
                    'list': MiniCheckinListSerializer(target_checkin_list).data,
                },
                status=201,
            )


class ExtendedBackend(DjangoFilterBackend):
    def get_filterset_kwargs(self, request, queryset, view):
        kwargs = super().get_filterset_kwargs(request, queryset, view)

        # merge filterset kwargs provided by view class
        if hasattr(view, 'get_filterset_kwargs'):
            kwargs.update(view.get_filterset_kwargs())

        return kwargs


class CheckinListPositionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CheckinListOrderPositionSerializer
    queryset = OrderPosition.all.none()
    filter_backends = (ExtendedBackend, RichOrderingFilter)
    ordering = ('attendee_name_cached', 'positionid')
    ordering_fields = (
        'order__code',
        'order__datetime',
        'positionid',
        'attendee_name',
        'last_checked_in',
        'order__email',
    )
    ordering_custom = {
        'attendee_name': {
            '_order': F('display_name').asc(nulls_first=True),
            'display_name': Coalesce('attendee_name_cached', 'addon_to__attendee_name_cached'),
        },
        '-attendee_name': {
            '_order': F('display_name').desc(nulls_last=True),
            'display_name': Coalesce('attendee_name_cached', 'addon_to__attendee_name_cached'),
        },
        'last_checked_in': {
            '_order': FixedOrderBy(F('last_checked_in'), nulls_first=True),
        },
        '-last_checked_in': {
            '_order': FixedOrderBy(F('last_checked_in'), nulls_last=True, descending=True),
        },
    }

    filterset_class = CheckinOrderPositionFilter
    permission = ('can_view_orders', 'can_checkin_orders')
    write_permission = ('can_change_orders', 'can_checkin_orders')

    def get_filterset_kwargs(self):
        return {
            'checkinlist': self.checkinlist,
        }

    @cached_property
    def checkinlist(self):
        try:
            return get_object_or_404(CheckinList, event=self.request.event, pk=self.kwargs.get('list'))
        except ValueError:
            raise Http404()

    def get_queryset(self, ignore_status=False, ignore_products=False):
        # Optional per-day filtering: limit check-ins to a specific date if provided
        selected_date = self.request.query_params.get('date')
        date_filter = {}
        if selected_date:
            from django.utils.dateparse import parse_date
            parsed = parse_date(selected_date)
            if parsed:
                date_filter = {'datetime__date': parsed}

        cqs = (
            Checkin.objects.filter(position_id=OuterRef('pk'), list_id=self.checkinlist.pk, **date_filter)
            .order_by()
            .values('position_id')
            .annotate(m=Max('datetime'))
            .values('m')
        )

        qs = (
            OrderPosition.objects.filter(
                order__event=self.request.event,
            )
            .annotate(last_checked_in=Subquery(cqs))
            .prefetch_related('order__event', 'order__event__organizer')
        )
        if self.checkinlist.subevent:
            qs = qs.filter(subevent=self.checkinlist.subevent)

        if self.request.query_params.get('ignore_status', 'false') != 'true' and not ignore_status:
            qs = qs.filter(
                order__status__in=[Order.STATUS_PAID, Order.STATUS_PENDING]
                if self.checkinlist.include_pending
                else [Order.STATUS_PAID]
            )
        if self.request.query_params.get('pdf_data', 'false') == 'true':
            qs = qs.prefetch_related(
                Prefetch(
                    lookup='checkins',
                    queryset=Checkin.objects.filter(list_id=self.checkinlist.pk, **date_filter),
                ),
                'checkins',
                'answers',
                'answers__options',
                'answers__question',
                Prefetch('addons', OrderPosition.objects.select_related('item', 'variation')),
                Prefetch(
                    'order',
                    Order.objects.select_related('invoice_address').prefetch_related(
                        Prefetch('event', Event.objects.select_related('organizer')),
                        Prefetch(
                            'positions',
                            OrderPosition.objects.prefetch_related(
                                'checkins',
                                'item',
                                'variation',
                                'answers',
                                'answers__options',
                                'answers__question',
                            ),
                        ),
                    ),
                ),
            ).select_related(
                'item',
                'variation',
                'item__category',
                'addon_to',
                'order',
                'order__invoice_address',
                'seat',
            )
        else:
            qs = qs.prefetch_related(
                Prefetch(
                    lookup='checkins',
                    queryset=Checkin.objects.filter(list_id=self.checkinlist.pk, **date_filter),
                ),
                'answers',
                'answers__options',
                'answers__question',
                Prefetch('addons', OrderPosition.objects.select_related('item', 'variation')),
            ).select_related(
                'item',
                'variation',
                'order',
                'addon_to',
                'order__invoice_address',
                'order',
                'seat',
            )

        if not self.checkinlist.all_products and not ignore_products:
            qs = qs.filter(item__in=self.checkinlist.limit_products.values_list('id', flat=True))

        if 'subevent' in self.request.query_params.getlist('expand'):
            qs = qs.prefetch_related(
                'subevent',
                'subevent__event',
                'subevent__subeventitem_set',
                'subevent__subeventitemvariation_set',
                'subevent__seat_category_mappings',
                'subevent__meta_values',
            )

        if 'item' in self.request.query_params.getlist('expand'):
            qs = qs.prefetch_related(
                'item',
                'item__addons',
                'item__bundles',
                'item__meta_values',
                'item__variations',
            ).select_related('item__tax_rule')

        if 'variation' in self.request.query_params.getlist('expand'):
            qs = qs.prefetch_related('variation')

        if (
            'pk' not in self.request.resolver_match.kwargs
            and 'can_view_orders' not in self.request.eventpermset
            and len(self.request.query_params.get('search', '')) < 3
        ):
            qs = qs.none()

        return qs

    @action(detail=False, methods=['POST'], url_name='redeem', url_path='(?P<pk>.*)/redeem')
    def redeem(self, *args, **kwargs):
        force = bool(self.request.data.get('force', False))
        type = self.request.data.get('type', None) or Checkin.TYPE_ENTRY
        if type not in dict(Checkin.CHECKIN_TYPES):
            raise BaseValidationError('Invalid check-in type.')
        ignore_unpaid = bool(self.request.data.get('ignore_unpaid', False))
        nonce = self.request.data.get('nonce')

        # Enforce inactive room blocking for gate-bound devices on entry scans
        if (
            type == Checkin.TYPE_ENTRY
            and isinstance(self.request.auth, Device)
            and getattr(self.request.auth, 'gate', None)
        ):
            gate = self.request.auth.gate
            # Enforce on the specific event in the current list context
            gate_room = Room.objects.filter(event=self.request.event, gates=gate).first()
            if gate_room and not gate_room.is_active:
                return Response(
                    {
                        'status': 'error',
                        'reason': 'room_inactive',
                        'reason_explanation': 'The room associated with this device gate is inactive.',
                        'gate': getattr(gate, 'pk', None),
                        'room': {
                            'id': gate_room.id,
                            'name': gate_room.name,
                            'is_active': gate_room.is_active,
                        },
                        'require_attention': False,
                        'checkin_texts': [],
                    },
                    status=400,
                )

        if 'datetime' in self.request.data:
            dt = DateTimeField().to_internal_value(self.request.data.get('datetime'))
        else:
            dt = now()

        try:
            queryset = self.get_queryset(ignore_status=True, ignore_products=True)
            if self.kwargs['pk'].isnumeric():
                op = queryset.get(Q(pk=self.kwargs['pk']) | Q(secret=self.kwargs['pk']))
            else:
                op = queryset.get(secret=self.kwargs['pk'])
        except OrderPosition.DoesNotExist:
            revoked_matches = list(self.request.event.revoked_secrets.filter(secret=self.kwargs['pk']))
            if len(revoked_matches) == 0 or not force:
                self.request.event.log_action(
                    'pretix.event.checkin.unknown',
                    data={
                        'datetime': dt,
                        'type': type,
                        'list': self.checkinlist.pk,
                        'barcode': self.kwargs['pk'],
                    },
                    user=self.request.user,
                    auth=self.request.auth,
                )
                raise Http404()

            op = revoked_matches[0].position
            op.order.log_action(
                'pretix.event.checkin.revoked',
                data={
                    'datetime': dt,
                    'type': type,
                    'list': self.checkinlist.pk,
                    'barcode': self.kwargs['pk'],
                },
                user=self.request.user,
                auth=self.request.auth,
            )

        given_answers = {}
        if 'answers' in self.request.data:
            aws = self.request.data.get('answers')
            for q in op.item.questions.filter(ask_during_checkin=True):
                if str(q.pk) in aws:
                    try:
                        if q.type == Question.TYPE_FILE:
                            given_answers[q] = self._handle_file_upload(aws[str(q.pk)])
                        else:
                            given_answers[q] = q.clean_answer(aws[str(q.pk)])
                    except BaseValidationError:
                        pass

        try:
            perform_checkin(
                op=op,
                clist=self.checkinlist,
                given_answers=given_answers,
                force=force,
                ignore_unpaid=ignore_unpaid,
                nonce=nonce,
                datetime=dt,
                questions_supported=self.request.data.get('questions_supported', True),
                canceled_supported=self.request.data.get('canceled_supported', False),
                user=self.request.user,
                auth=self.request.auth,
                type=type,
            )
        except RequiredQuestionsError as e:
            return Response(
                {
                    'status': 'incomplete',
                    'require_attention': op.item.checkin_attention or op.order.checkin_attention,
                    'position': CheckinListOrderPositionSerializer(op, context=self.get_serializer_context()).data,
                    'questions': [QuestionSerializer(q).data for q in e.questions],
                },
                status=400,
            )
        except CheckInError as e:
            op.order.log_action(
                'pretix.event.checkin.denied',
                data={
                    'position': op.id,
                    'positionid': op.positionid,
                    'errorcode': e.code,
                    'force': force,
                    'datetime': dt,
                    'type': type,
                    'list': self.checkinlist.pk,
                },
                user=self.request.user,
                auth=self.request.auth,
            )
            return Response(
                {
                    'status': 'error',
                    'reason': e.code,
                    'require_attention': op.item.checkin_attention or op.order.checkin_attention,
                    'position': CheckinListOrderPositionSerializer(op, context=self.get_serializer_context()).data,
                },
                status=400,
            )
        else:
            return Response(
                {
                    'status': 'ok',
                    'require_attention': op.item.checkin_attention or op.order.checkin_attention,
                    'position': CheckinListOrderPositionSerializer(op, context=self.get_serializer_context()).data,
                },
                status=201,
            )

    def _handle_file_upload(self, data):
        try:
            cf = CachedFile.objects.get(
                session_key=f'api-upload-{str(type(self.request.user or self.request.auth))}-{(self.request.user or self.request.auth).pk}',
                file__isnull=False,
                pk=data[len('file:') :],
            )
        except (BaseValidationError, IndexError):  # invalid uuid
            raise BaseValidationError('The submitted file ID "{fid}" was not found.'.format(fid=data))
        except CachedFile.DoesNotExist:
            raise BaseValidationError('The submitted file ID "{fid}" was not found.'.format(fid=data))

        allowed_types = ('image/png', 'image/jpeg', 'image/gif', 'application/pdf')
        if cf.type not in allowed_types:
            raise BaseValidationError(
                'The submitted file "{fid}" has a file type that is not allowed in this field.'.format(fid=data)
            )
        if cf.file.size > 10 * 1024 * 1024:
            raise BaseValidationError(
                'The submitted file "{fid}" is too large to be used in this field.'.format(fid=data)
            )

        return cf.file


class CheckinRedeemView(views.APIView):
    def post(self, request, *args, **kwargs):
        auth = self.request.auth
        user = self.request.user

        if isinstance(auth, (TeamAPIToken, Device)):
            events = auth.get_events_with_permission(('can_change_orders', 'can_checkin_orders'))
        elif user.is_authenticated:
            events = user.get_events_with_permission(('can_change_orders', 'can_checkin_orders'), request).filter(
                organizer=self.request.organizer
            )
        else:
            raise ValueError('Unknown authentication method')
        serializer = CheckinRedeemInputSerializer(data=request.data, context={'events': events, 'request': request})
        serializer.is_valid(raise_exception=True)
        return _redeem_process(
            checkinlists=serializer.validated_data['lists'],
            raw_barcode=serializer.validated_data['secret'],
            source_type=serializer.validated_data['source_type'],
            answers_data=serializer.validated_data.get('answers'),
            dateandtime=serializer.validated_data.get('datetime') or now(),
            force=serializer.validated_data['force'],
            checkin_type=serializer.validated_data['type'],
            ignore_unpaid=serializer.validated_data['ignore_unpaid'],
            nonce=serializer.validated_data.get('nonce'),
            untrusted_input=True,
            user=user,
            auth=auth,
            expand=self.request.query_params.getlist('expand'),
            pdf_data=self.request.query_params.get('pdf_data', 'false') == 'true',
            questions_supported=serializer.validated_data['questions_supported'],
            canceled_supported=True,
            request=self.request,
            legacy_url_support=False,
        )


class EventCheckoutView(views.APIView):
    """
    API endpoint to checkout all attendees for an entire event.
    This will create exit checkins for all currently checked-in attendees.
    """
    permission_classes = ('can_change_orders', 'can_checkin_orders')

    def post(self, request, *args, **kwargs):
        from django.conf import settings
        
        auth = request.auth
        user = request.user
        event = request.event

        # Validate permissions
        if isinstance(auth, (TeamAPIToken, Device)):
            events = auth.get_events_with_permission(('can_change_orders', 'can_checkin_orders'))
        elif user.is_authenticated:
            events = user.get_events_with_permission(
                ('can_change_orders', 'can_checkin_orders'), request
            ).filter(organizer=request.organizer)
        else:
            raise PermissionDenied('Authentication required')

        if event not in events:
            raise PermissionDenied('You do not have permission to checkout attendees for this event.')

        # Get all checkin lists for this event
        checkin_lists = event.checkin_lists.all()
        
        if not checkin_lists.exists():
            return Response(
                {'error': 'No check-in lists found for this event.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Prepare task arguments
        user_id = user.pk if user.is_authenticated else None
        auth_id = None
        auth_type = None
        
        if isinstance(auth, TeamAPIToken):
            auth_id = auth.pk
            auth_type = 'TeamAPIToken'
        elif isinstance(auth, Device):
            auth_id = auth.pk
            auth_type = 'Device'

        # Check if Celery is available for background processing
        if settings.HAS_CELERY:
            # Run as background task
            task_result = bulk_checkout_task.apply_async(
                kwargs={
                    'event_id': event.pk,
                    'user_id': user_id,
                    'auth_id': auth_id,
                    'auth_type': auth_type,
                },
                queue='background'  # Use background queue for long-running tasks
            )
            
            return Response({
                'status': 'accepted',
                'message': 'Bulk checkout has been queued for background processing.',
                'task_id': task_result.id,
                'note': 'Use the task_id to check the status of the operation.'
            }, status=status.HTTP_202_ACCEPTED)
        else:
            # Run synchronously if Celery is not available
            result = bulk_checkout_task(
                event_id=event.pk,
                user_id=user_id,
                auth_id=auth_id,
                auth_type=auth_type,
            )
            
            return Response(
                result,
                status=status.HTTP_200_OK if result['status'] == 'success' else status.HTTP_207_MULTI_STATUS
            )


class CheckinSearchView(ListAPIView):
    serializer_class = CheckinListOrderPositionSerializer
    queryset = OrderPosition.all.none()
    filter_backends = (ExtendedBackend, RichOrderingFilter)
    ordering = (F('attendee_name_cached').asc(nulls_last=True), 'positionid')
    ordering_fields = (
        'order__code',
        'order__datetime',
        'positionid',
        'attendee_name',
        'last_checked_in',
        'order__email',
    )
    ordering_custom = {
        'attendee_name': {
            '_order': F('display_name').asc(nulls_first=True),
            'display_name': Coalesce('attendee_name_cached', 'addon_to__attendee_name_cached'),
        },
        '-attendee_name': {
            '_order': F('display_name').desc(nulls_last=True),
            'display_name': Coalesce('attendee_name_cached', 'addon_to__attendee_name_cached'),
        },
        'last_checked_in': {
            '_order': OrderBy(F('last_checked_in'), nulls_first=True),
        },
        '-last_checked_in': {
            '_order': OrderBy(F('last_checked_in'), nulls_last=True, descending=True),
        },
    }
    filterset_class = OrderPositionFilter

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({'expand': self.request.query_params.getlist('expand'), 'pdf_data': False})
        return context

    @cached_property
    def lists(self):
        auth = self.request.auth
        user = self.request.user

        if isinstance(auth, (TeamAPIToken, Device)):
            events = auth.get_events_with_permission(('can_view_orders', 'can_checkin_orders'))
        elif user.is_authenticated:
            events = user.get_events_with_permission(('can_view_orders', 'can_checkin_orders'), self.request).filter(
                organizer=self.request.organizer
            )
        else:
            raise ValueError('Unknown authentication method')

        requested_list_ids = [
            int(list_id) for list_id in self.request.query_params.getlist('list') if list_id.isdigit()
        ]
        checkin_lists = CheckinList.objects.filter(event__in=events, id__in=requested_list_ids).select_related('event')

        if len(checkin_lists) != len(requested_list_ids):
            missing_lists = set(requested_list_ids) - {lst.pk for lst in checkin_lists}
            raise PermissionDenied(f'Access denied or non-existent lists: {", ".join(map(str, missing_lists))}')

        return list(checkin_lists)

    @cached_property
    def has_full_access_permission(self):
        auth = self.request.auth
        user = self.request.user

        if isinstance(auth, (TeamAPIToken, Device)):
            events = auth.get_events_with_permission('can_view_orders')
        elif user.is_authenticated:
            events = user.get_events_with_permission('can_view_orders', self.request).filter(
                organizer=self.request.organizer
            )
        else:
            raise ValueError('Unknown authentication method')

        return CheckinList.objects.filter(
            event__in=events, id__in=[checkin_list.pk for checkin_list in self.lists]
        ).count() == len(self.lists)

    def get_queryset(self, ignore_status=False, ignore_products=False):
        params = self.request.query_params
        search_term = params.get('search', '')
        search_len = len(search_term)
        min_search_len = 3

        queryset = _checkin_list_position_queryset(
            self.lists,
            ignore_status=params.get('ignore_status', 'false') == 'true' or ignore_status,
            ignore_products=ignore_products,
            pdf_data=params.get('pdf_data', 'false') == 'true',
            expand=params.getlist('expand'),
        )

        # If no search term is provided, return empty queryset for security
        if not search_term:
            return queryset.none()
        
        # For users without full access, require minimum search length
        # But still allow search if they have proper permissions for the lists
        if search_len < min_search_len and not self.has_full_access_permission():
            return queryset.none()

        return queryset
