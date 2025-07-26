import json
import logging
from contextlib import suppress
from urllib.parse import urlparse

import django_filters
import jwt
import requests
from asgiref.sync import async_to_sync
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, Q
from django.forms.models import model_to_dict
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.crypto import get_random_string
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_filters.rest_framework import DjangoFilterBackend, FilterSet
from django_scopes import scopes_disabled
from rest_framework import exceptions, filters, serializers, views, viewsets
from rest_framework.authentication import get_authorization_header
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from eventyay.base.api.auth import (
    ApiAccessRequiredPermission,
    UserDeletePermissions,
    EventPermissions,
)
from eventyay.api.serializers.rooms import EventSerializer
from eventyay.base.models import Channel, User
from eventyay.base.services.event import notify_schedule_change, notify_event_change

from eventyay.base.models.event import Event
from pretix.api.auth.permission import EventCRUDPermission
from pretix.api.serializers.event import (
    CloneEventSerializer,
    DeviceEventSettingsSerializer,
    EventSerializer as PretixEventSerializer,
    EventSettingsSerializer,
    SubEventSerializer,
    TaxRuleSerializer,
)
from pretix.api.views import ConditionalListView
from pretix.base.models import (
    CartPosition,
    Device,
    Order,
    Organizer,
    TaxRule,
    TeamAPIToken,
)
from pretix.base.models.event import SubEvent
from pretix.base.settings import SETTINGS_AFFECTING_CSS
from pretix.helpers.dicts import merge_dicts
from pretix.presale.style import regenerate_css
from pretix.presale.views.organizer import filter_qs_by_attr
from .task import configure_video_settings_for_talks
from .utils import get_protocol

logger = logging.getLogger(__name__)

with scopes_disabled():

    class EventFilter(FilterSet):
        is_past = django_filters.rest_framework.BooleanFilter(method='is_past_qs')
        is_future = django_filters.rest_framework.BooleanFilter(method='is_future_qs')
        ends_after = django_filters.rest_framework.IsoDateTimeFilter(method='ends_after_qs')
        sales_channel = django_filters.rest_framework.CharFilter(method='sales_channel_qs')

        class Meta:
            model = Event
            fields = ['is_public', 'live', 'has_subevents']

        def ends_after_qs(self, queryset, name, value):
            expr = Q(has_subevents=False) & Q(
                Q(Q(date_to__isnull=True) & Q(date_from__gte=value))
                | Q(Q(date_to__isnull=False) & Q(date_to__gte=value))
            )
            return queryset.filter(expr)

        def is_past_qs(self, queryset, name, value):
            expr = Q(has_subevents=False) & Q(
                Q(Q(date_to__isnull=True) & Q(date_from__lt=now())) | Q(Q(date_to__isnull=False) & Q(date_to__lt=now()))
            )
            if value:
                return queryset.filter(expr)
            else:
                return queryset.exclude(expr)

        def is_future_qs(self, queryset, name, value):
            expr = Q(has_subevents=False) & Q(
                Q(Q(date_to__isnull=True) & Q(date_from__gte=now()))
                | Q(Q(date_to__isnull=False) & Q(date_to__gte=now()))
            )
            if value:
                return queryset.filter(expr)
            else:
                return queryset.exclude(expr)

        def sales_channel_qs(self, queryset, name, value):
            return queryset.filter(sales_channels__contains=value)


class EventViewSet(viewsets.ModelViewSet):
    serializer_class = PretixEventSerializer
    queryset = Event.objects.none()
    lookup_field = 'slug'
    lookup_url_kwarg = 'event'
    lookup_value_regex = '[^/]+'
    permission_classes = (EventCRUDPermission,)
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    ordering = ('slug',)
    ordering_fields = ('date_from', 'slug')
    filterset_class = EventFilter

    def get_queryset(self):
        if isinstance(self.request.auth, (TeamAPIToken, Device)):
            qs = self.request.auth.get_events_with_any_permission()
        elif self.request.user.is_authenticated:
            qs = self.request.user.get_events_with_any_permission(self.request).filter(organizer=self.request.organizer)

        qs = filter_qs_by_attr(qs, self.request)
        return qs.prefetch_related('meta_values', 'meta_values__property', 'seat_category_mappings')

    def perform_update(self, serializer):
        current_live_value = serializer.instance.live
        updated_live_value = serializer.validated_data.get('live', None)
        current_plugins_value = serializer.instance.get_plugins()
        updated_plugins_value = serializer.validated_data.get('plugins', None)

        super().perform_update(serializer)

        if updated_live_value is not None and updated_live_value != current_live_value:
            log_action = 'pretix.event.live.activated' if updated_live_value else 'pretix.event.live.deactivated'
            serializer.instance.log_action(
                log_action,
                user=self.request.user,
                auth=self.request.auth,
                data=self.request.data,
            )

        if updated_plugins_value is not None and set(updated_plugins_value) != set(current_plugins_value):
            enabled = {m: 'enabled' for m in updated_plugins_value if m not in current_plugins_value}
            disabled = {m: 'disabled' for m in current_plugins_value if m not in updated_plugins_value}
            changed = merge_dicts(enabled, disabled)

            for module, action in changed.items():
                serializer.instance.log_action(
                    'pretix.event.plugins.' + action,
                    user=self.request.user,
                    auth=self.request.auth,
                    data={'plugin': module},
                )

        other_keys = {k: v for k, v in serializer.validated_data.items() if k not in ['plugins', 'live']}
        if other_keys:
            serializer.instance.log_action(
                'pretix.event.changed',
                user=self.request.user,
                auth=self.request.auth,
                data=self.request.data,
            )

    def perform_create(self, serializer):
        serializer.save(organizer=self.request.organizer)
        serializer.instance.set_defaults()
        serializer.instance.log_action(
            'pretix.event.added',
            user=self.request.user,
            auth=self.request.auth,
            data=self.request.data,
        )

    def perform_destroy(self, instance):
        if not instance.allow_delete():
            raise PermissionDenied(
                "The event can not be deleted as it already contains orders. Please set 'live'"
                ' to false to hide the event and take the shop offline instead.'
            )
        try:
            with transaction.atomic():
                instance.organizer.log_action(
                    'pretix.event.deleted',
                    user=self.request.user,
                    data={
                        'event_id': instance.pk,
                        'name': str(instance.name),
                        'logentries': list(instance.logentry_set.values_list('pk', flat=True)),
                    },
                )
                instance.delete_sub_objects()
                super().perform_destroy(instance)
        except ProtectedError:
            raise PermissionDenied(
                'The event could not be deleted as some constraints (e.g. data created by plug-ins) do not allow it.'
            )


class CloneEventViewSet(viewsets.ModelViewSet):
    serializer_class = CloneEventSerializer
    queryset = Event.objects.none()
    lookup_field = 'slug'
    lookup_url_kwarg = 'event'
    http_method_names = ['post']
    write_permission = 'can_create_events'

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['event'] = self.kwargs['event']
        ctx['organizer'] = self.request.organizer
        return ctx

    def perform_create(self, serializer):
        serializer.save(organizer=self.request.organizer)

        serializer.instance.log_action(
            'pretix.event.added',
            user=self.request.user,
            auth=self.request.auth,
            data=self.request.data,
        )


with scopes_disabled():

    class SubEventFilter(FilterSet):
        is_past = django_filters.rest_framework.BooleanFilter(method='is_past_qs')
        is_future = django_filters.rest_framework.BooleanFilter(method='is_future_qs')
        ends_after = django_filters.rest_framework.IsoDateTimeFilter(method='ends_after_qs')
        modified_since = django_filters.IsoDateTimeFilter(field_name='last_modified', lookup_expr='gte')

        class Meta:
            model = SubEvent
            fields = ['active', 'event__live']

        def ends_after_qs(self, queryset, name, value):
            expr = Q(
                Q(Q(date_to__isnull=True) & Q(date_from__gte=value))
                | Q(Q(date_to__isnull=False) & Q(date_to__gte=value))
            )
            return queryset.filter(expr)

        def is_past_qs(self, queryset, name, value):
            expr = Q(
                Q(Q(date_to__isnull=True) & Q(date_from__lt=now())) | Q(Q(date_to__isnull=False) & Q(date_to__lt=now()))
            )
            if value:
                return queryset.filter(expr)
            else:
                return queryset.exclude(expr)

        def is_future_qs(self, queryset, name, value):
            expr = Q(
                Q(Q(date_to__isnull=True) & Q(date_from__gte=now()))
                | Q(Q(date_to__isnull=False) & Q(date_to__gte=now()))
            )
            if value:
                return queryset.filter(expr)
            else:
                return queryset.exclude(expr)


class SubEventViewSet(ConditionalListView, viewsets.ModelViewSet):
    serializer_class = SubEventSerializer
    queryset = SubEvent.objects.none()
    write_permission = 'can_change_event_settings'
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filterset_class = SubEventFilter
    ordering = ('date_from',)
    ordering_fields = ('id', 'date_from', 'last_modified')

    def get_queryset(self):
        if getattr(self.request, 'event', None):
            qs = self.request.event.subevents
        elif isinstance(self.request.auth, (TeamAPIToken, Device)):
            qs = SubEvent.objects.filter(
                event__organizer=self.request.organizer,
                event__in=self.request.auth.get_events_with_any_permission(),
            )
        elif self.request.user.is_authenticated:
            qs = SubEvent.objects.filter(
                event__organizer=self.request.organizer,
                event__in=self.request.user.get_events_with_any_permission(),
            )

        qs = filter_qs_by_attr(qs, self.request)

        return qs.prefetch_related(
            'subeventitem_set',
            'subeventitemvariation_set',
            'seat_category_mappings',
            'meta_values',
        )

    def list(self, request, **kwargs):
        date = serializers.DateTimeField().to_representation(now())
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            resp = self.get_paginated_response(serializer.data)
            resp['X-Page-Generated'] = date
            return resp

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, headers={'X-Page-Generated': date})

    def perform_update(self, serializer):
        original_data = self.get_serializer(instance=serializer.instance).data
        super().perform_update(serializer)

        if serializer.data == original_data:
            # Performance optimization: If nothing was changed, we do not need to save or log anything.
            # This costs us a few cycles on save, but avoids thousands of lines in our log.
            return

        serializer.instance.log_action(
            'pretix.subevent.changed',
            user=self.request.user,
            auth=self.request.auth,
            data=self.request.data,
        )

    def perform_create(self, serializer):
        serializer.save(event=self.request.event)
        serializer.instance.log_action(
            'pretix.subevent.added',
            user=self.request.user,
            auth=self.request.auth,
            data=self.request.data,
        )

    def perform_destroy(self, instance):
        if not instance.allow_delete():
            raise PermissionDenied(
                'The sub-event can not be deleted as it has already been used in orders. Please set'
                " 'active' to false instead to hide it from users."
            )
        try:
            with transaction.atomic():
                instance.log_action(
                    'pretix.subevent.deleted',
                    user=self.request.user,
                    auth=self.request.auth,
                    data=self.request.data,
                )
                CartPosition.objects.filter(addon_to__subevent=instance).delete()
                instance.cartposition_set.all().delete()
                super().perform_destroy(instance)
        except ProtectedError:
            raise PermissionDenied(
                'The sub-event could not be deleted as some constraints (e.g. data created by '
                'plug-ins) do not allow it.'
            )


class TaxRuleViewSet(ConditionalListView, viewsets.ModelViewSet):
    serializer_class = TaxRuleSerializer
    queryset = TaxRule.objects.none()
    write_permission = 'can_change_event_settings'

    def get_queryset(self):
        return self.request.event.tax_rules.all()

    def perform_update(self, serializer):
        super().perform_update(serializer)
        serializer.instance.log_action(
            'pretix.event.taxrule.changed',
            user=self.request.user,
            auth=self.request.auth,
            data=self.request.data,
        )

    def perform_create(self, serializer):
        serializer.save(event=self.request.event)
        serializer.instance.log_action(
            'pretix.event.taxrule.added',
            user=self.request.user,
            auth=self.request.auth,
            data=self.request.data,
        )

    def perform_destroy(self, instance):
        if not instance.allow_delete():
            raise PermissionDenied('This tax rule can not be deleted as it is currently in use.')

        instance.log_action(
            'pretix.event.taxrule.deleted',
            user=self.request.user,
            auth=self.request.auth,
        )
        super().perform_destroy(instance)


class EventSettingsView(views.APIView):
    permission = None
    write_permission = 'can_change_event_settings'

    def get(self, request, *args, **kwargs):
        if isinstance(request.auth, Device):
            s = DeviceEventSettingsSerializer(
                instance=request.event.settings,
                event=request.event,
                context={'request': request},
            )
        elif 'can_change_event_settings' in request.eventpermset:
            s = EventSettingsSerializer(
                instance=request.event.settings,
                event=request.event,
                context={'request': request},
            )
        else:
            raise PermissionDenied()
        if 'explain' in request.GET:
            return Response(
                {
                    fname: {
                        'value': s.data[fname],
                        'label': getattr(field, '_label', fname),
                        'help_text': getattr(field, '_help_text', None),
                    }
                    for fname, field in s.fields.items()
                }
            )
        return Response(s.data)

    def patch(self, request, *wargs, **kwargs):
        s = EventSettingsSerializer(
            instance=request.event.settings,
            data=request.data,
            partial=True,
            event=request.event,
            context={'request': request},
        )
        s.is_valid(raise_exception=True)
        with transaction.atomic():
            s.save()
            self.request.event.log_action(
                'pretix.event.settings',
                user=self.request.user,
                auth=self.request.auth,
                data={k: v for k, v in s.validated_data.items()},
            )
        if any(p in s.changed_data for p in SETTINGS_AFFECTING_CSS):
            regenerate_css.apply_async(args=(request.event.pk,))
        s = EventSettingsSerializer(
            instance=request.event.settings,
            event=request.event,
            context={'request': request},
        )
        return Response(s.data)


def check_token_permission(token, permission_required):
    # Decode and validate the JWT token
    decoded_data = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
    # Check if user existed
    User.objects.get(email=decoded_data['email'])
    if decoded_data.get('has_perms') not in permission_required:
        return False
    return True


@csrf_exempt
@require_POST
@scopes_disabled()
def talk_schedule_public(request, *args, **kwargs):
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        try:
            if not check_token_permission(token, 'orga.edit_schedule'):
                return JsonResponse(
                    {'status': 'User does not have permission to show schedule on menu'},
                    status=403,
                )
            organiser = get_object_or_404(Organizer, slug=kwargs['organizer'])
            event = get_object_or_404(Event, slug=kwargs['event'], organizer=organiser)
            request_data = json.loads(request.body)
            event.settings.talk_schedule_public = request_data.get('is_show_schedule') or False

            return JsonResponse({'status': 'success'}, status=200)

        except jwt.ExpiredSignatureError:
            logger.error('Token has expired')
            return JsonResponse({'status': 'Token has expired'}, status=401)
        except jwt.InvalidTokenError:
            logger.error('Invalid token')
            return JsonResponse({'status': 'Invalid token'}, status=401)
        except Organizer.DoesNotExist:
            logger.error('Organizer not found')
            return JsonResponse({'status': 'Organizer not found'}, status=404)
        except Event.DoesNotExist:
            logger.error('Event not found')
            return JsonResponse({'status': 'Event not found'}, status=404)
        except Exception as e:
            logger.error('Internal server error: %s', e)
            return JsonResponse({'status': 'Internal server error'}, status=500)
    else:
        logger.error('Authorization header missing or invalid')
        return JsonResponse({'status': 'Authorization header missing or invalid'}, status=403)


class CustomerOrderCheckView(APIView):
    authentication_classes = ()
    permission_classes = ()

    @scopes_disabled()
    def post(self, request, *args, **kwargs):
        if not kwargs.get('event') or not kwargs.get('organizer'):
            return Response(status=400, data={'error': 'Missing parameters.'})

        try:
            organizer = Organizer.objects.get(slug=kwargs['organizer'])
            event = Event.objects.get(slug=kwargs['event'], organizer=organizer)
            user = User.objects.get(email__iexact=request.data.get('user_email'))

        except Organizer.DoesNotExist:
            return JsonResponse(status=404, data={'error': 'Organizer not found.'})
        except Event.DoesNotExist:
            return JsonResponse(status=404, data={'error': 'Event not found.'})
        except User.DoesNotExist:
            return JsonResponse(status=404, data={'error': 'Customer not found.'})

        # Get all orders of customer which belong to this event
        order_list = (
            Order.objects.filter(Q(event=event) & (Q(email__iexact=user.email)))
            .select_related('event')
            .order_by('-datetime')
        )

        if not order_list:
            return JsonResponse(status=404, data={'error': 'Customer has no orders for this event.'})

        for order in order_list:
            if order.status == 'p':
                return JsonResponse(status=200, data={'message': 'Customer has paid orders.'})

        return JsonResponse(status=400, data={'message': 'Customer did not paid orders.'})


class EventView(APIView):
    permission_classes = [ApiAccessRequiredPermission & EventPermissions]

    def get(self, request, **kwargs):
        return Response(EventSerializer(request.event).data)

    @transaction.atomic
    def patch(self, request, **kwargs):
        serializer = EventSerializer(request.event, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        transaction.on_commit(  # pragma: no cover
            lambda: async_to_sync(notify_event_change)(request.event.id)
        )
        return Response(serializer.data)


class EventThemeView(APIView):
    permission_classes = []

    def get(self, request, **kwargs):
        """
        Retrieve theme config of an event
        @param request: request obj
        @param kwargs: event_id
        @return: theme data of an event
        """
        try:
            event = get_object_or_404(Event, id=kwargs["event_id"])
            return Response(EventSerializer(event).data["config"]["theme"])
        except KeyError:
            logger.error(
                "error happened when trying to get theme data of event: %s",
                kwargs["event_id"],
            )
            return Response(
                "error happened when trying to get theme data of event: "
                + kwargs["event_id"],
                status=503,
            )


class CreateEventView(APIView):
    authentication_classes = []  # disables authentication
    permission_classes = []

    @staticmethod
    def post(request, *args, **kwargs) -> JsonResponse:
        payload = CreateEventView.get_payload_from_token(request)

        # check if user has permission to create event
        if payload.get("has_permission"):
            secret = get_random_string(length=64)
            config = {
                "JWT_secrets": [
                    {
                        "issuer": "any",
                        "audience": "eventyay",
                        "secret": secret,
                    }
                ]
            }

            titles = request.data.get("title") or {}
            locale = request.data.get("locale")

            title_values = [value for value in titles.values() if value]
            title_default = title_values[0] if title_values else ""

            title = titles.get(locale) or titles.get("en") or title_default

            attendee_trait_grants = request.data.get("traits", {}).get("attendee", "")
            if not isinstance(attendee_trait_grants, str):
                raise ValidationError("Attendee traits must be a string")

            trait_grants = {
                "admin": ["admin"],
                "attendee": (
                    [attendee_trait_grants] if attendee_trait_grants else ["attendee"]
                ),
                "scheduleuser": ["schedule-update"],
            }

            # if event already exists, update it, otherwise create a new event
            event_id = request.data.get("id")
            domain_path = "{}{}/{}".format(
                settings.DOMAIN_PATH,
                settings.BASE_PATH,
                request.data.get("id"),
            )
            try:
                if not event_id:
                    raise ValidationError("Event ID is required")
                if Event.objects.filter(id=event_id).exists():
                    event = Event.objects.get(id=event_id)
                    event.title = title
                    event.domain = domain_path
                    event.locale = request.data.get("locale") or "en"
                    event.timezone = request.data.get("timezone") or "UTC"
                    event.trait_grants = trait_grants
                    event.save()
                else:
                    event = Event.objects.create(
                        id=event_id,
                        title=title,
                        domain=domain_path,
                        locale=request.data.get("locale") or "en",
                        timezone=request.data.get("timezone") or "UTC",
                        config=config,
                        trait_grants=trait_grants,
                    )
                configure_video_settings_for_talks.delay(
                    event_id, days=30, number=1, traits=["schedule-update"], long=True
                )
                site_url = settings.SITE_URL
                protocol = get_protocol(site_url)
                event.domain = "{}://{}".format(protocol, domain_path)
                return JsonResponse(model_to_dict(event, exclude=["roles"]), status=201)
            except IntegrityError as e:
                logger.error(f"Database integrity error while saving event: {e}")
                return JsonResponse(
                    {
                        "error": "An event with this ID already exists or database constraint violated"
                    },
                    status=400,
                )
            except ValidationError as e:
                logger.error(f"Validation error while saving event: {e}")
                return JsonResponse({"error": str(e)}, status=400)
            except Exception as e:
                logger.error(f"Unexpected error creating event: {e}")
                return JsonResponse(
                    {"error": "An unexpected error occurred"}, status=500
                )
        else:
            return JsonResponse(
                {"error": "Event cannot be created due to missing permission"},
                status=403,
            )

    @staticmethod
    def get_payload_from_token(request):
        auth_header = get_authorization_header(request).split()
        if auth_header and auth_header[0].lower() == b"bearer":
            if len(auth_header) == 1:
                raise exceptions.AuthenticationFailed(
                    "Invalid token header. No credentials provided."
                )
            elif len(auth_header) > 2:
                raise exceptions.AuthenticationFailed(
                    "Invalid token header. Token string should not contain spaces."
                )
        try:
            payload = jwt.decode(
                auth_header[1], settings.SECRET_KEY, algorithms=["HS256"]
            )
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed("Token has expired")
        except jwt.DecodeError:
            raise exceptions.AuthenticationFailed("Invalid token")
        return payload


class UserFavouriteView(APIView):
    permission_classes = []

    @staticmethod
    def post(request, *args, **kwargs) -> JsonResponse:
        """
        Handle POST requests to add talks to the user's favourite list.
        Being called by eventyay-talk, authenticate by bearer token.
        """
        try:
            talk_list = json.loads(request.body.decode())
            user_code = UserFavouriteView.get_uid_from_token(
                request, kwargs["event_id"]
            )
            user = User.objects.get(token_id=user_code)
            if not user_code or not user:
                # user not created yet, no error should be returned
                logger.error("User not found for adding favourite talks.")
                return JsonResponse([], safe=False, status=200)
            if user.client_state is None:
                # If it's None, create a new dictionary with schedule.favs field
                user.client_state = {"schedule": {"favs": talk_list}}
            else:
                # If client_state is not None, check if 'schedule' field exists
                if "schedule" not in user.client_state:
                    # If 'schedule' field doesn't exist, create it
                    user.client_state["schedule"] = {"favs": talk_list}
                else:
                    # If 'schedule' field exists, update the 'favs' field
                    user.client_state["schedule"]["favs"] = talk_list
            user.save()
            return JsonResponse(talk_list, safe=False, status=200)
        except Exception as e:
            logger.error(
                "error happened when trying to add fav talks: %s",
                kwargs["event_id"],
            )
            logger.error(e)
            # Since this is called from background so no error should be returned
            return JsonResponse([], safe=False, status=200)

    @staticmethod
    def get_uid_from_token(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        auth_header = get_authorization_header(request).split()
        if auth_header and auth_header[0].lower() == b"bearer":
            if len(auth_header) == 1:
                raise exceptions.AuthenticationFailed(
                    "Invalid token header. No credentials provided."
                )
            elif len(auth_header) > 2:
                raise exceptions.AuthenticationFailed(
                    "Invalid token header. Token string should not contain spaces."
                )
        token_decode = event.decode_token(token=auth_header[1])
        return token_decode.get("uid")


class ExportView(APIView):
    permission_classes = []

    @staticmethod
    def get(request, *args, **kwargs):
        export_type = request.GET.get("export_type", "json")
        event = get_object_or_404(Event, id=kwargs["event_id"])
        talk_config = event.config.get("pretalx")
        user = User.objects.filter(token_id=request.user)
        talk_base_url = (
            talk_config.get("domain")
            + "/"
            + talk_config.get("event")
            + "/schedule/export/"
        )
        export_endpoint = "schedule." + export_type
        talk_url = talk_base_url + export_endpoint
        if "my" in export_type and user:
            user_state = user.first().client_state
            if (
                user_state
                and user_state.get("schedule")
                and user_state.get("schedule").get("favs")
            ):
                talk_list = user_state.get("schedule").get("favs")
                talk_list_str = ",".join(talk_list)
                export_endpoint = "schedule-my." + export_type.replace("my", "")
                talk_url = talk_base_url + export_endpoint + "?talks=" + talk_list_str
        header = {"Content-Type": "application/json"}
        response = requests.get(talk_url, headers=header)
        return Response(response.content.decode("utf-8"))


def get_domain(path):
    if not path:
        return ""
    domain = urlparse(path).netloc
    if ":" in domain:
        domain = domain.split(":")[0]
    return domain.lower()


@api_view(http_method_names=["POST"])
@permission_classes([ApiAccessRequiredPermission])
def schedule_update(request, **kwargs):
    """POST endpoint to notify eventyay that schedule data has changed.

    Optionally, the request may contain data for the ``pretalx`` field in the
    event config.
    """
    domain = get_domain(request.data.get("domain"))
    event = request.data.get("event")

    if not domain or not event:
        return Response("Missing fields in request.", status=401)

    pretalx_config = request.event.config.get("pretalx", {})
    if domain != get_domain(
        pretalx_config.get("domain")
    ) or event != pretalx_config.get("event"):
        return Response("Incorrect domain or event data", status=401)

    # We assume that only pretalx uses this endpoint
    request.event.config["pretalx"]["connected"] = True
    request.event.config["pretalx"]["pushed"] = now().isoformat()
    request.event.save()

    async_to_sync(notify_schedule_change)(request.event.id)
    return Response(status=200)


@api_view(http_method_names=["POST"])
@permission_classes([UserDeletePermissions])
def delete_user(request, **kwargs):
    """POST endpoint to soft-delete a user.

    This endpoint is called with a single POST parameter, 'user_id'."""
    user_id = request.data.get("user_id")
    token_id = request.data.get("token_id")
    if not user_id and not token_id:
        return Response("Missing user ID.", status=400)
    if user_id and token_id:
        return Response("Ambiguous user ID.", status=400)

    user = None
    with suppress(exceptions.ValidationError):  # raised when user_id isn't a uid
        if user_id:
            user = User.objects.filter(id=user_id, deleted=False).first()
        elif token_id:
            user = User.objects.filter(token_id=token_id, deleted=False).first()
    if not user:
        return Response(status=404)

    user.soft_delete()
    return Response(status=204)