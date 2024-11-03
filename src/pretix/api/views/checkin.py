import django_filters
import operator
from functools import reduce
from django.core.exceptions import ValidationError as BaseValidationError
from django.db.models import (
    Count, Exists, F, Max, OuterRef, Prefetch, Q, Subquery, OrderBy,prefetch_related_objects
)
from django.db.models.functions import Coalesce
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext, gettext_lazy
from django_filters.rest_framework import DjangoFilterBackend, FilterSet
from django_scopes import scopes_disabled
from rest_framework import views, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.fields import DateTimeField
from rest_framework.response import Response
from rest_framework.generics import ListAPIView

from pretix.api.serializers.checkin import CheckinListSerializer,CheckinRPCRedeemInputSerializer, MiniCheckinListSerializer
from pretix.api.serializers.item import QuestionSerializer
from pretix.api.serializers.order import CheckinListOrderPositionSerializer
from pretix.api.views import RichOrderingFilter
from pretix.api.views.order import OrderPositionFilter
from pretix.base.i18n import language
from pretix.base.models import (
    CachedFile, Checkin, CheckinList, Event, Order, OrderPosition, Question, Device, TeamAPIToken, RevokedTicketSecret,
)
from pretix.base.services.checkin import (
    CheckInError, RequiredQuestionsError, SQLLogic, perform_checkin,
)
from pretix.helpers.database import FixedOrderBy

with scopes_disabled():
    class CheckinListFilter(FilterSet):
        subevent_match = django_filters.NumberFilter(method='subevent_match_qs')
        ends_after = django_filters.rest_framework.IsoDateTimeFilter(method='ends_after_qs')

        class Meta:
            model = CheckinList
            fields = ['subevent']

        def subevent_match_qs(self, qs, name, value):
            return qs.filter(
                Q(subevent_id=value) | Q(subevent_id__isnull=True)
            )

        def ends_after_qs(self, queryset, name, value):
            expr = (
                Q(subevent__isnull=True) |
                Q(
                    Q(Q(subevent__date_to__isnull=True) & Q(subevent__date_from__gte=value))
                    | Q(Q(subevent__date_to__isnull=False) & Q(subevent__date_to__gte=value))
                )
            )
            return queryset.filter(expr)


class CheckinListViewSet(viewsets.ModelViewSet):
    serializer_class = CheckinListSerializer
    queryset = CheckinList.objects.none()
    filter_backends = (DjangoFilterBackend,)
    filterset_class = CheckinListFilter
    permission = ('can_view_orders', 'can_checkin_orders',)
    write_permission = 'can_change_event_settings'

    def get_queryset(self):
        qs = self.request.event.checkin_lists.prefetch_related(
            'limit_products',
        )

        if 'subevent' in self.request.query_params.getlist('expand'):
            qs = qs.prefetch_related(
                'subevent', 'subevent__event', 'subevent__subeventitem_set', 'subevent__subeventitemvariation_set',
                'subevent__seat_category_mappings', 'subevent__meta_values'
            )
        return qs

    def perform_create(self, serializer):
        serializer.save(event=self.request.event)
        serializer.instance.log_action(
            'pretix.event.checkinlist.added',
            user=self.request.user,
            auth=self.request.auth,
            data=self.request.data
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
            data=self.request.data
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
                checkedin=Exists(Checkin.objects.filter(list_id=clist.pk, position=OuterRef('pk'), type=Checkin.TYPE_ENTRY))
            ).filter(
                checkedin=True,
            )
            pqs = clist.positions

            ev = clist.subevent or clist.event
            response = {
                'event': {
                    'name': str(ev.name),
                },
                'checkin_count': cqs.count(),
                'position_count': pqs.count(),
                'inside_count': clist.inside_count,
            }

            op_by_item = {
                p['item']: p['cnt']
                for p in pqs.order_by().values('item').annotate(cnt=Count('id'))
            }
            op_by_variation = {
                p['variation']: p['cnt']
                for p in pqs.order_by().values('variation').annotate(cnt=Count('id'))
            }
            c_by_item = {
                p['item']: p['cnt']
                for p in cqs.order_by().values('item').annotate(cnt=Count('id'))
            }
            c_by_variation = {
                p['variation']: p['cnt']
                for p in cqs.order_by().values('variation').annotate(cnt=Count('id'))
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
                    'variations': []
                }
                for var in item.variations.all():
                    i['variations'].append({
                        'id': var.pk,
                        'value': str(var),
                        'checkin_count': c_by_variation.get(var.pk, 0),
                        'position_count': op_by_variation.get(var.pk, 0),
                    })
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


def _checkin_list_position_queryset(checkinlists, ignore_status=False, ignore_products=False, pdf_data=False, expand=None):
    list_by_event = {cl.event_id: cl for cl in checkinlists}
    if not checkinlists:
        raise BaseValidationError('No check-in list passed.')
    if len(list_by_event) != len(checkinlists):
        raise BaseValidationError('Selecting two check-in lists from the same event is unsupported.')

    cqs = Checkin.objects.filter(
        position_id=OuterRef('pk'),
        list_id__in=[cl.pk for cl in checkinlists]
    ).order_by().values('position_id').annotate(
        m=Max('datetime')
    ).values('m')

    qs = OrderPosition.objects.filter(
        order__event__in=list_by_event.keys(),
    ).annotate(
        last_checked_in=Subquery(cqs)
    ).prefetch_related('order__event', 'order__event__organizer')

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
                    Q(order__status=Order.STATUS_PAID) |
                    Q(order__status=Order.STATUS_PENDING, order__valid_if_pending=True)
                )
        if not checkinlist.all_products and not ignore_products:
            list_q &= Q(item__in=checkinlist.limit_products.values_list('id', flat=True))
        lists_qs.append(list_q)

    qs = qs.filter(reduce(operator.or_, lists_qs))

    if pdf_data:
        qs = qs.prefetch_related(
            Prefetch(
                lookup='checkins',
                queryset=Checkin.objects.filter(list_id__in=[cl.pk for cl in checkinlists])
            ),
            'answers', 'answers__options', 'answers__question',
            Prefetch('addons', OrderPosition.objects.select_related('item', 'variation')),
            Prefetch('order', Order.objects.select_related('invoice_address').prefetch_related(
                Prefetch(
                    'event',
                    Event.objects.select_related('organizer')
                ),
                Prefetch(
                    'positions',
                    OrderPosition.objects.prefetch_related(
                        Prefetch('checkins', queryset=Checkin.objects.all()),
                        'item', 'variation', 'answers', 'answers__options', 'answers__question',
                    )
                )
            ))
        ).select_related(
            'item', 'variation', 'item__category', 'addon_to', 'order', 'order__invoice_address', 'seat'
        )
    else:
        qs = qs.prefetch_related(
            Prefetch(
                lookup='checkins',
                queryset=Checkin.objects.filter(list_id__in=[cl.pk for cl in checkinlists])
            ),
            'answers', 'answers__options', 'answers__question',
            Prefetch('addons', OrderPosition.objects.select_related('item', 'variation'))
        ).select_related('item', 'variation', 'order', 'addon_to', 'order__invoice_address', 'order', 'seat')

    if expand and 'subevent' in expand:
        qs = qs.prefetch_related(
            'subevent', 'subevent__event', 'subevent__subeventitem_set', 'subevent__subeventitemvariation_set',
            'subevent__seat_category_mappings', 'subevent__meta_values'
        )

    if expand and 'item' in expand:
        qs = qs.prefetch_related('item', 'item__addons', 'item__bundles', 'item__meta_values',
                                 'item__variations').select_related('item__tax_rule')

    if expand and 'variation' in expand:
        qs = qs.prefetch_related('variation', 'variation__meta_values')

    return qs


def _handle_file_upload(data, user, auth):
    try:
        cf = CachedFile.objects.get(
            session_key=f'api-upload-{str(type(user or auth))}-{(user or auth).pk}',
            file__isnull=False,
            pk=data[len("file:"):],
        )
    except (BaseValidationError, BaseBaseValidationError, IndexError):  # invalid uuid
        raise BaseValidationError('The submitted file ID "{fid}" was not found.'.format(fid=data))
    except CachedFile.DoesNotExist:
        raise BaseValidationError('The submitted file ID "{fid}" was not found.'.format(fid=data))

    allowed_types = (
        'image/png', 'image/jpeg', 'image/gif', 'application/pdf'
    )
    if cf.type not in allowed_types:
        raise BaseValidationError('The submitted file "{fid}" has a file type that is not allowed in this field.'.format(fid=data))
    if cf.file.size > settings.FILE_UPLOAD_MAX_SIZE_OTHER:
        raise BaseValidationError('The submitted file "{fid}" is too large to be used in this field.'.format(fid=data))

    return cf.file

def _redeem_process(*, checkinlists, raw_barcode, answers_data, datetime, force, checkin_type, ignore_unpaid, nonce,
                    untrusted_input, user, auth, expand, pdf_data, request, questions_supported, canceled_supported,
                    source_type='barcode', legacy_url_support=False, simulate=False, gate=None):
    if not checkinlists:
        raise BaseValidationError('No check-in list passed.')

    list_by_event = {checkinlist.event_id: checkinlist for checkinlist in checkinlists}
    prefetch_related_objects([checkinlist for checkinlist in checkinlists if not checkinlist.all_products], 'limit_products') # prefetch_related

    device = auth if isinstance(auth, Device) else None
    gate = gate or (auth.gate if isinstance(auth, Device) else None)

    context = {
            'request': request,
            'expand': expand,
    }

    def _make_context(context, event):
        return{
            **context,
            'event': event,
            'pdf_data': pdf_data and (
                user if user and user.is_authenticated else auth
            ).has_event_permission(request.organizer, event, 'can_view_orders', request),
        }

    common_checkin_args = dict(
        raw_barcode=raw_barcode,
        raw_source_type=source_type,
        type=checkin_type,
        list=checkinlists[0],
        datetime=datetime,
        device=device,
        gate=gate,
        nonce=nonce,
        forced=force,
    )
    raw_barcode_for_checkin = None
    from_revoked_secret = False
    if simulate:
        common_checkin_args['__fake_arg_to_prevent_this_from_being_saved'] = True

    queryset = _checkin_list_position_queryset(checkinlists, pdf_data=pdf_data, ignore_status=True, ignore_products=True).order_by(
        F('addon_to').asc(nulls_first=True)
    )



    q = Q(secret=raw_barcode)

    if raw_barcode.isnumeric() and not untrusted_input and legacy_url_support:
        q |= Q(pk=raw_barcode)


    op_candidates = list(queryset.filter(q)) #filtering queryset with q to fetch orderposition

    print('\n',op_candidates,'\n')

    op = op_candidates[0]
    common_checkin_args['list'] = list_by_event[op.order.event_id]

    # 5. Pre-validate all incoming answers, handle file upload
    given_answers = {}
    if answers_data:
        for q in op.item.questions.filter(ask_during_checkin=True):
            if str(q.pk) in answers_data:
                try:
                    if q.type == Question.TYPE_FILE:
                        given_answers[q] = _handle_file_upload(answers_data[str(q.pk)], user, auth)
                    else:
                        given_answers[q] = q.clean_answer(answers_data[str(q.pk)])
                except (BaseValidationError):
                    pass

    with language(op.order.event.settings.locale):
        try:
            perform_checkin(
                    op=op,
                    clist=list_by_event[op.order.event_id],
                    given_answers=given_answers,
                    force=force,
                    ignore_unpaid=ignore_unpaid,
                    nonce=nonce,
                    datetime=datetime,
                    questions_supported=questions_supported,
                    canceled_supported=canceled_supported,
                    user=user,
                    auth=auth,
                    type=checkin_type,
            )
        except RequiredQuestionsError as e:
            return Response({
                'status': 'incomplete',
                'require_attention': op.require_checkin_attention,
                'position': CheckinListOrderPositionSerializer(op, context=_make_context(context, op.order.event)).data,
                'questions': [
                    QuestionSerializer(q).data for q in e.questions
                ],
                'list': MiniCheckinListSerializer(list_by_event[op.order.event_id]).data,
            }, status=400)
        except CheckInError as e:
            if not simulate:
                op.order.log_action('pretix.event.checkin.denied', data={
                    'position': op.id,
                    'positionid': op.positionid,
                    'errorcode': e.code,
                    'reason_explanation': e.reason,
                    'force': force,
                    'datetime': datetime,
                    'type': checkin_type,
                    'list': list_by_event[op.order.event_id].pk,
                }, user=user, auth=auth)
                Checkin.objects.create(
                    position=op,
                    successful=False,
                    error_reason=e.code,
                    error_explanation=e.reason,
                    **common_checkin_args,
                )
            return Response({
                'status': 'error',
                'reason': e.code,
                'reason_explanation': e.reason,
                'require_attention': op.require_checkin_attention,
                'position': CheckinListOrderPositionSerializer(op, context=_make_context(context, op.order.event)).data,
                'list': MiniCheckinListSerializer(list_by_event[op.order.event_id]).data,
            }, status=400)
        else:
            return Response({
                'status': 'ok',
                'require_attention': op.require_checkin_attention,
                'position': CheckinListOrderPositionSerializer(op, context=_make_context(context, op.order.event)).data,
                'list': MiniCheckinListSerializer(list_by_event[op.order.event_id]).data,
            }, status=201)



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
        'order__code', 'order__datetime', 'positionid', 'attendee_name',
        'last_checked_in', 'order__email',
    )
    ordering_custom = {
        'attendee_name': {
            '_order': F('display_name').asc(nulls_first=True),
            'display_name': Coalesce('attendee_name_cached', 'addon_to__attendee_name_cached')
        },
        '-attendee_name': {
            '_order': F('display_name').desc(nulls_last=True),
            'display_name': Coalesce('attendee_name_cached', 'addon_to__attendee_name_cached')
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
            return get_object_or_404(CheckinList, event=self.request.event, pk=self.kwargs.get("list"))
        except ValueError:
            raise Http404()

    def get_queryset(self, ignore_status=False, ignore_products=False):
        cqs = Checkin.objects.filter(
            position_id=OuterRef('pk'),
            list_id=self.checkinlist.pk
        ).order_by().values('position_id').annotate(
            m=Max('datetime')
        ).values('m')

        qs = OrderPosition.objects.filter(
            order__event=self.request.event,
        ).annotate(
            last_checked_in=Subquery(cqs)
        ).prefetch_related('order__event', 'order__event__organizer')
        if self.checkinlist.subevent:
            qs = qs.filter(
                subevent=self.checkinlist.subevent
            )

        if self.request.query_params.get('ignore_status', 'false') != 'true' and not ignore_status:
            qs = qs.filter(
                order__status__in=[Order.STATUS_PAID, Order.STATUS_PENDING] if self.checkinlist.include_pending else [Order.STATUS_PAID]
            )
        if self.request.query_params.get('pdf_data', 'false') == 'true':
            qs = qs.prefetch_related(
                Prefetch(
                    lookup='checkins',
                    queryset=Checkin.objects.filter(list_id=self.checkinlist.pk)
                ),
                'checkins', 'answers', 'answers__options', 'answers__question',
                Prefetch('addons', OrderPosition.objects.select_related('item', 'variation')),
                Prefetch('order', Order.objects.select_related('invoice_address').prefetch_related(
                    Prefetch(
                        'event',
                        Event.objects.select_related('organizer')
                    ),
                    Prefetch(
                        'positions',
                        OrderPosition.objects.prefetch_related(
                            'checkins', 'item', 'variation', 'answers', 'answers__options', 'answers__question',
                        )
                    )
                ))
            ).select_related(
                'item', 'variation', 'item__category', 'addon_to', 'order', 'order__invoice_address', 'seat'
            )
        else:
            qs = qs.prefetch_related(
                Prefetch(
                    lookup='checkins',
                    queryset=Checkin.objects.filter(list_id=self.checkinlist.pk)
                ),
                'answers', 'answers__options', 'answers__question',
                Prefetch('addons', OrderPosition.objects.select_related('item', 'variation'))
            ).select_related('item', 'variation', 'order', 'addon_to', 'order__invoice_address', 'order', 'seat')

        if not self.checkinlist.all_products and not ignore_products:
            qs = qs.filter(item__in=self.checkinlist.limit_products.values_list('id', flat=True))

        if 'subevent' in self.request.query_params.getlist('expand'):
            qs = qs.prefetch_related(
                'subevent', 'subevent__event', 'subevent__subeventitem_set', 'subevent__subeventitemvariation_set',
                'subevent__seat_category_mappings', 'subevent__meta_values'
            )

        if 'item' in self.request.query_params.getlist('expand'):
            qs = qs.prefetch_related('item', 'item__addons', 'item__bundles', 'item__meta_values', 'item__variations').select_related('item__tax_rule')

        if 'variation' in self.request.query_params.getlist('expand'):
            qs = qs.prefetch_related('variation')

        if 'pk' not in self.request.resolver_match.kwargs and 'can_view_orders' not in self.request.eventpermset \
                and len(self.request.query_params.get('search', '')) < 3:
            qs = qs.none()

        return qs

    @action(detail=False, methods=['POST'], url_name='redeem', url_path='(?P<pk>.*)/redeem')
    def redeem(self, *args, **kwargs):
        force = bool(self.request.data.get('force', False))
        type = self.request.data.get('type', None) or Checkin.TYPE_ENTRY
        if type not in dict(Checkin.CHECKIN_TYPES):
            raise BaseValidationError("Invalid check-in type.")
        ignore_unpaid = bool(self.request.data.get('ignore_unpaid', False))
        nonce = self.request.data.get('nonce')

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
                self.request.event.log_action('pretix.event.checkin.unknown', data={
                    'datetime': dt,
                    'type': type,
                    'list': self.checkinlist.pk,
                    'barcode': self.kwargs['pk']
                }, user=self.request.user, auth=self.request.auth)
                raise Http404()

            op = revoked_matches[0].position
            op.order.log_action('pretix.event.checkin.revoked', data={
                'datetime': dt,
                'type': type,
                'list': self.checkinlist.pk,
                'barcode': self.kwargs['pk']
            }, user=self.request.user, auth=self.request.auth)

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
            return Response({
                'status': 'incomplete',
                'require_attention': op.item.checkin_attention or op.order.checkin_attention,
                'position': CheckinListOrderPositionSerializer(op, context=self.get_serializer_context()).data,
                'questions': [
                    QuestionSerializer(q).data for q in e.questions
                ]
            }, status=400)
        except CheckInError as e:
            op.order.log_action('pretix.event.checkin.denied', data={
                'position': op.id,
                'positionid': op.positionid,
                'errorcode': e.code,
                'force': force,
                'datetime': dt,
                'type': type,
                'list': self.checkinlist.pk
            }, user=self.request.user, auth=self.request.auth)
            return Response({
                'status': 'error',
                'reason': e.code,
                'require_attention': op.item.checkin_attention or op.order.checkin_attention,
                'position': CheckinListOrderPositionSerializer(op, context=self.get_serializer_context()).data
            }, status=400)
        else:
            return Response({
                'status': 'ok',
                'require_attention': op.item.checkin_attention or op.order.checkin_attention,
                'position': CheckinListOrderPositionSerializer(op, context=self.get_serializer_context()).data
            }, status=201)

    def _handle_file_upload(self, data):
        try:
            cf = CachedFile.objects.get(
                session_key=f'api-upload-{str(type(self.request.user or self.request.auth))}-{(self.request.user or self.request.auth).pk}',
                file__isnull=False,
                pk=data[len("file:"):],
            )
        except (BaseValidationError, IndexError):  # invalid uuid
            raise BaseValidationError('The submitted file ID "{fid}" was not found.'.format(fid=data))
        except CachedFile.DoesNotExist:
            raise BaseValidationError('The submitted file ID "{fid}" was not found.'.format(fid=data))

        allowed_types = (
            'image/png', 'image/jpeg', 'image/gif', 'application/pdf'
        )
        if cf.type not in allowed_types:
            raise BaseValidationError('The submitted file "{fid}" has a file type that is not allowed in this field.'.format(fid=data))
        if cf.file.size > 10 * 1024 * 1024:
            raise BaseValidationError('The submitted file "{fid}" is too large to be used in this field.'.format(fid=data))

        return cf.file

class CheckinRPCRedeemView(views.APIView):
    def post(self, request, *args, **kwargs):
        auth = self.request.auth
        user = self.request.user

        if isinstance(auth, (TeamAPIToken, Device)):
            events = auth.get_events_with_permission(('can_change_orders', 'can_checkin_orders'))
        elif user.is_authenticated:
            events = user.get_events_with_permission(('can_change_orders', 'can_checkin_orders'), request).filter(organizer=self.request.organizer)
        else:
            raise ValueError("Unknown authentication method")

        serializer = CheckinRPCRedeemInputSerializer(data=request.data, context={'events': events})
        serializer.is_valid(raise_exception=True)
        return _redeem_process(
            checkinlists=serializer.validated_data['lists'],
            raw_barcode=serializer.validated_data['secret'],
            source_type=serializer.validated_data['source_type'],
            answers_data=serializer.validated_data.get('answers'),
            datetime=serializer.validated_data.get('datetime') or now(),
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


class CheckinRPCSearchView(ListAPIView):
    serializer_class = CheckinListOrderPositionSerializer
    queryset = OrderPosition.all.none()
    filter_backends = (ExtendedBackend, RichOrderingFilter)
    ordering = (F('attendee_name_cached').asc(nulls_last=True), 'positionid')
    ordering_fields = (
        'order__code', 'order__datetime', 'positionid', 'attendee_name',
        'last_checked_in', 'order__email',
    )
    ordering_custom = {
        'attendee_name': {
            '_order': F('display_name').asc(nulls_first=True),
            'display_name': Coalesce('attendee_name_cached', 'addon_to__attendee_name_cached')
        },
        '-attendee_name': {
            '_order': F('display_name').desc(nulls_last=True),
            'display_name': Coalesce('attendee_name_cached', 'addon_to__attendee_name_cached')
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
        return {
            **super().get_serializer_context(),
            'expand': self.request.query_params.getlist('expand'),
            'pdf_data': False
        }

    @cached_property
    def lists(self):
        auth = self.request.auth
        user = self.request.user

        if isinstance(auth, (TeamAPIToken, Device)):
            events = auth.get_events_with_permission(('can_view_orders', 'can_checkin_orders'))
        elif user.is_authenticated:
            events = user.get_events_with_permission(('can_view_orders', 'can_checkin_orders'), self.request).filter(organizer=self.request.organizer)
        else:
            raise ValueError("Unknown authentication method")

        requested_lists = [int(l) for l in self.request.query_params.getlist('list') if l.isdigit()]
        checkin_lists = CheckinList.objects.filter(event__in=events, id__in=requested_lists).select_related('event')

        if len(checkin_lists) != len(requested_lists):
            missing_lists = set(requested_lists) - {l.pk for l in checkin_lists}
            raise PermissionDenied(f"Access denied or non-existent lists: {', '.join(map(str, missing_lists))}")

        return list(checkin_lists)

    @cached_property
    def has_full_access_permission(self):
        auth = self.request.auth
        user = self.request.user

        if isinstance(auth, (TeamAPIToken, Device)):
            events = auth.get_events_with_permission('can_view_orders')
        elif user.is_authenticated:
            events = user.get_events_with_permission('can_view_orders', self.request).filter(organizer=self.request.organizer)
        else:
            raise ValueError("Unknown authentication method")

        return CheckinList.objects.filter(event__in=events, id__in=[c.pk for c in self.lists]).count() == len(self.lists)

    def get_queryset(self, ignore_status=False, ignore_products=False):
        params = self.request.query_params
        min_search_len = 3
        search_len = len(params.get('search', ''))

        qs = _checkin_list_position_queryset(
            self.lists,
            ignore_status=params.get('ignore_status', 'false') == 'true' or ignore_status,
            ignore_products=ignore_products,
            pdf_data=params.get('pdf_data', 'false') == 'true',
            expand=params.getlist('expand'),
        )

        if search_len < min_search_len and not self.has_full_access_permission:
            qs = qs.none()

        return qs
