from decimal import Decimal

import django_filters
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property
from django_filters.rest_framework import DjangoFilterBackend, FilterSet
from django_scopes import scopes_disabled
from rest_framework import (
    filters, mixins, serializers, status, views, viewsets,
)
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied
from rest_framework.mixins import CreateModelMixin, DestroyModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from pretix.api.models import OAuthAccessToken
from pretix.api.serializers.organizer import (
    CustomerCreateSerializer, CustomerSerializer, DeviceSerializer,
    GiftCardSerializer, GiftCardTransactionSerializer, OrganizerSerializer,
    OrganizerSettingsSerializer, SeatingPlanSerializer, TeamAPITokenSerializer,
    TeamInviteSerializer, TeamMemberSerializer, TeamSerializer,
)
from pretix.base.models import (
    Customer, Device, GiftCard, GiftCardTransaction, Organizer, SeatingPlan,
    Team, TeamAPIToken, TeamInvite, User,
)
from pretix.base.settings import SETTINGS_AFFECTING_CSS
from pretix.helpers.dicts import merge_dicts
from pretix.presale.style import regenerate_organizer_css


class OrganizerViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrganizerSerializer
    queryset = Organizer.objects.none()
    lookup_field = 'slug'
    lookup_url_kwarg = 'organizer'
    lookup_value_regex = '[^/]+'
    filter_backends = (filters.OrderingFilter,)
    ordering = ('slug',)
    ordering_fields = ('name', 'slug')

    def get_queryset(self):
        if self.request.user.is_authenticated:
            if self.request.user.has_active_staff_session(self.request.session.session_key):
                return Organizer.objects.all()
            elif isinstance(self.request.auth, OAuthAccessToken):
                return Organizer.objects.filter(
                    pk__in=self.request.user.teams.values_list('organizer', flat=True)
                ).filter(
                    pk__in=self.request.auth.organizers.values_list('pk', flat=True)
                )
            else:
                return Organizer.objects.filter(pk__in=self.request.user.teams.values_list('organizer', flat=True))
        elif hasattr(self.request.auth, 'organizer_id'):
            return Organizer.objects.filter(pk=self.request.auth.organizer_id)
        else:
            return Organizer.objects.filter(pk=self.request.auth.team.organizer_id)


class SeatingPlanViewSet(viewsets.ModelViewSet):
    serializer_class = SeatingPlanSerializer
    queryset = SeatingPlan.objects.none()
    permission = 'can_change_organizer_settings'
    write_permission = 'can_change_organizer_settings'

    def get_queryset(self):
        return self.request.organizer.seating_plans.order_by('name')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['organizer'] = self.request.organizer
        return ctx

    @transaction.atomic()
    def perform_create(self, serializer):
        inst = serializer.save(organizer=self.request.organizer)
        self.request.organizer.log_action(
            'pretix.seatingplan.added',
            user=self.request.user,
            auth=self.request.auth,
            data=merge_dicts(self.request.data, {'id': inst.pk})
        )

    @transaction.atomic()
    def perform_update(self, serializer):
        if serializer.instance.events.exists() or serializer.instance.subevents.exists():
            raise PermissionDenied('This plan can not be changed while it is in use for an event.')
        inst = serializer.save(organizer=self.request.organizer)
        self.request.organizer.log_action(
            'pretix.seatingplan.changed',
            user=self.request.user,
            auth=self.request.auth,
            data=merge_dicts(self.request.data, {'id': serializer.instance.pk})
        )
        return inst

    @transaction.atomic()
    def perform_destroy(self, instance):
        if instance.events.exists() or instance.subevents.exists():
            raise PermissionDenied('This plan can not be deleted while it is in use for an event.')
        instance.log_action(
            'pretix.seatingplan.deleted',
            user=self.request.user,
            auth=self.request.auth,
            data={'id': instance.pk}
        )
        instance.delete()


with scopes_disabled():
    class GiftCardFilter(FilterSet):
        secret = django_filters.CharFilter(field_name='secret', lookup_expr='iexact')

        class Meta:
            model = GiftCard
            fields = ['secret', 'testmode']


class GiftCardViewSet(viewsets.ModelViewSet):
    serializer_class = GiftCardSerializer
    queryset = GiftCard.objects.none()
    permission = 'can_manage_gift_cards'
    write_permission = 'can_manage_gift_cards'
    filter_backends = (DjangoFilterBackend,)
    filterset_class = GiftCardFilter

    def get_queryset(self):
        if self.request.GET.get('include_accepted') == 'true':
            qs = self.request.organizer.accepted_gift_cards
        else:
            qs = self.request.organizer.issued_gift_cards.all()
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['organizer'] = self.request.organizer
        return ctx

    @transaction.atomic()
    def perform_create(self, serializer):
        value = serializer.validated_data.pop('value')
        inst = serializer.save(issuer=self.request.organizer)
        inst.transactions.create(value=value)
        inst.log_action(
            'pretix.giftcards.transaction.manual',
            user=self.request.user,
            auth=self.request.auth,
            data=merge_dicts(self.request.data, {'id': inst.pk})
        )

    @transaction.atomic()
    def perform_update(self, serializer):
        if 'include_accepted' in self.request.GET:
            raise PermissionDenied("Accepted gift cards cannot be updated, use transact instead.")
        GiftCard.objects.select_for_update().get(pk=self.get_object().pk)
        old_value = serializer.instance.value
        value = serializer.validated_data.pop('value')
        inst = serializer.save(secret=serializer.instance.secret, currency=serializer.instance.currency,
                               testmode=serializer.instance.testmode)
        diff = value - old_value
        inst.transactions.create(value=diff)
        inst.log_action(
            'pretix.giftcards.transaction.manual',
            user=self.request.user,
            auth=self.request.auth,
            data={'value': diff}
        )
        return inst

    @action(detail=True, methods=["POST"])
    @transaction.atomic()
    def transact(self, request, **kwargs):
        gc = GiftCard.objects.select_for_update().get(pk=self.get_object().pk)
        value = serializers.DecimalField(max_digits=10, decimal_places=2).to_internal_value(
            request.data.get('value')
        )
        text = serializers.CharField(allow_blank=True, allow_null=True).to_internal_value(
            request.data.get('text', '')
        )
        if gc.value + value < Decimal('0.00'):
            return Response({
                'value': ['The gift card does not have sufficient credit for this operation.']
            }, status=status.HTTP_409_CONFLICT)
        gc.transactions.create(value=value, text=text)
        gc.log_action(
            'pretix.giftcards.transaction.manual',
            user=self.request.user,
            auth=self.request.auth,
            data={'value': value, 'text': text}
        )
        return Response(GiftCardSerializer(gc).data, status=status.HTTP_200_OK)

    def perform_destroy(self, instance):
        raise MethodNotAllowed("Gift cards cannot be deleted.")


class GiftCardTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = GiftCardTransactionSerializer
    queryset = GiftCardTransaction.objects.none()
    permission = 'can_manage_gift_cards'
    write_permission = 'can_manage_gift_cards'

    @cached_property
    def giftcard(self):
        if self.request.GET.get('include_accepted') == 'true':
            qs = self.request.organizer.accepted_gift_cards
        else:
            qs = self.request.organizer.issued_gift_cards.all()
        return get_object_or_404(qs, pk=self.kwargs.get('giftcard'))

    def get_queryset(self):
        return self.giftcard.transactions.select_related('order', 'order__event')


class TeamViewSet(viewsets.ModelViewSet):
    serializer_class = TeamSerializer
    queryset = Team.objects.none()
    permission = 'can_change_teams'
    write_permission = 'can_change_teams'

    def get_queryset(self):
        return self.request.organizer.teams.order_by('pk')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['organizer'] = self.request.organizer
        return ctx

    @transaction.atomic()
    def perform_create(self, serializer):
        inst = serializer.save(organizer=self.request.organizer)
        inst.log_action(
            'pretix.team.created',
            user=self.request.user,
            auth=self.request.auth,
            data=merge_dicts(self.request.data, {'id': inst.pk})
        )

    @transaction.atomic()
    def perform_update(self, serializer):
        inst = serializer.save()
        inst.log_action(
            'pretix.team.changed',
            user=self.request.user,
            auth=self.request.auth,
            data=self.request.data
        )
        return inst

    def perform_destroy(self, instance):
        instance.log_action('pretix.team.deleted', user=self.request.user, auth=self.request.auth)
        instance.delete()


class TeamMemberViewSet(DestroyModelMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = TeamMemberSerializer
    queryset = User.objects.none()
    permission = 'can_change_teams'
    write_permission = 'can_change_teams'

    @cached_property
    def team(self):
        return get_object_or_404(self.request.organizer.teams, pk=self.kwargs.get('team'))

    def get_queryset(self):
        return self.team.members.all()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['organizer'] = self.request.organizer
        return ctx

    @transaction.atomic()
    def perform_destroy(self, instance):
        self.team.members.remove(instance)
        self.team.log_action(
            'pretix.team.member.removed', user=self.request.user, auth=self.request.auth, data={
                'email': instance.email,
                'user': instance.pk
            }
        )


class TeamInviteViewSet(CreateModelMixin, DestroyModelMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = TeamInviteSerializer
    queryset = TeamInvite.objects.none()
    permission = 'can_change_teams'
    write_permission = 'can_change_teams'

    @cached_property
    def team(self):
        return get_object_or_404(self.request.organizer.teams, pk=self.kwargs.get('team'))

    def get_queryset(self):
        return self.team.invites.order_by('email')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['organizer'] = self.request.organizer
        ctx['team'] = self.team
        ctx['log_kwargs'] = {
            'user': self.request.user,
            'auth': self.request.auth,
        }
        return ctx

    @transaction.atomic()
    def perform_destroy(self, instance):
        self.team.log_action(
            'pretix.team.invite.deleted', user=self.request.user, auth=self.request.auth, data={
                'email': instance.email,
            }
        )
        instance.delete()

    @transaction.atomic()
    def perform_create(self, serializer):
        serializer.save(team=self.team)


class TeamAPITokenViewSet(CreateModelMixin, DestroyModelMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = TeamAPITokenSerializer
    queryset = TeamAPIToken.objects.none()
    permission = 'can_change_teams'
    write_permission = 'can_change_teams'

    @cached_property
    def team(self):
        return get_object_or_404(self.request.organizer.teams, pk=self.kwargs.get('team'))

    def get_queryset(self):
        return self.team.tokens.order_by('name')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['organizer'] = self.request.organizer
        ctx['team'] = self.team
        ctx['log_kwargs'] = {
            'user': self.request.user,
            'auth': self.request.auth,
        }
        return ctx

    @transaction.atomic()
    def perform_destroy(self, instance):
        instance.active = False
        instance.save()
        self.team.log_action(
            'pretix.team.token.deleted', user=self.request.user, auth=self.request.auth, data={
                'name': instance.name,
            }
        )

    @transaction.atomic()
    def perform_create(self, serializer):
        instance = serializer.save(team=self.team)
        self.team.log_action(
            'pretix.team.token.created', auth=self.request.auth, user=self.request.user, data={
                'name': instance.name,
                'id': instance.pk
            }
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        d = serializer.data
        d['token'] = serializer.instance.token
        return Response(d, status=status.HTTP_201_CREATED, headers=headers)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        serializer = self.get_serializer_class()(instance)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_200_OK, headers=headers)


class DeviceViewSet(mixins.CreateModelMixin,
                    mixins.RetrieveModelMixin,
                    mixins.UpdateModelMixin,
                    mixins.ListModelMixin,
                    GenericViewSet):
    serializer_class = DeviceSerializer
    queryset = Device.objects.none()
    permission = 'can_change_organizer_settings'
    write_permission = 'can_change_organizer_settings'
    lookup_field = 'device_id'

    def get_queryset(self):
        return self.request.organizer.devices.order_by('pk')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['organizer'] = self.request.organizer
        return ctx

    @transaction.atomic()
    def perform_create(self, serializer):
        inst = serializer.save(organizer=self.request.organizer)
        inst.log_action(
            'pretix.device.created',
            user=self.request.user,
            auth=self.request.auth,
            data=merge_dicts(self.request.data, {'id': inst.pk})
        )

    @transaction.atomic()
    def perform_update(self, serializer):
        inst = serializer.save()
        inst.log_action(
            'pretix.device.changed',
            user=self.request.user,
            auth=self.request.auth,
            data=self.request.data
        )
        return inst


class OrganizerSettingsView(views.APIView):
    permission = 'can_change_organizer_settings'

    def get(self, request, *args, **kwargs):
        s = OrganizerSettingsSerializer(instance=request.organizer.settings, organizer=request.organizer, context={
            'request': request
        })
        if 'explain' in request.GET:
            return Response({
                fname: {
                    'value': s.data[fname],
                    'label': getattr(field, '_label', fname),
                    'help_text': getattr(field, '_help_text', None)
                } for fname, field in s.fields.items()
            })
        return Response(s.data)

    def patch(self, request, *wargs, **kwargs):
        s = OrganizerSettingsSerializer(
            instance=request.organizer.settings, data=request.data, partial=True,
            organizer=request.organizer, context={
                'request': request
            }
        )
        s.is_valid(raise_exception=True)
        with transaction.atomic():
            s.save()
            self.request.organizer.log_action(
                'pretix.organizer.settings', user=self.request.user, auth=self.request.auth, data={
                    k: v for k, v in s.validated_data.items()
                }
            )
        if any(p in s.changed_data for p in SETTINGS_AFFECTING_CSS):
            regenerate_organizer_css.apply_async(args=(request.organizer.pk,))
        s = OrganizerSettingsSerializer(instance=request.organizer.settings, organizer=request.organizer, context={
            'request': request
        })
        return Response(s.data)


with scopes_disabled():
    """
        Filter for Customer model based on the email field.

        Attributes:
            email (django_filters.CharFilter): A case-insensitive exact match filter for the email field.

        Meta:
            model (Customer): The model to filter.
            fields (list): The fields to filter by.
    """
    class CustomerFilter(FilterSet):
        email = django_filters.CharFilter(field_name='email', lookup_expr='iexact')

        class Meta:
            model = Customer
            fields = ['email']


class CustomerViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerSerializer
    queryset = Customer.objects.none()
    # Manage customers permission is required to access this view
    permission = 'can_manage_customers'
    lookup_field = 'identifier'
    filter_backends = (DjangoFilterBackend,)
    filterset_class = CustomerFilter

    def get_queryset(self):
        """
        Get the list of customers.
        @return: customers
        """
        return self.request.organizer.customers.all()

    def get_serializer_context(self):
        """
        Get the serializer context.
        @return:
        """
        context = super().get_serializer_context()
        context['organizer'] = self.request.organizer
        return context

    def perform_destroy(self, instance):
        raise MethodNotAllowed("Customers cannot be deleted.")

    @transaction.atomic()
    def perform_create(self, serializer, send_email=False):
        """
        Create a new customer.
        @param serializer: serializer instance
        @param send_email: allow to send mail or not
        @return: created customer
        """
        customer = serializer.save(organizer=self.request.organizer, password=make_password(None))
        # Log the action
        serializer.instance.log_action(
            'eventyay.customer.created',
            user=self.request.user,
            auth=self.request.auth,
            data=self.request.data,
        )
        if send_email:
            # Send activation mail for customer to activate the account
            customer.send_activation_mail()
        return customer

    def create(self, request, *args, **kwargs):
        """
        Creates a new Customer instance based on the request data.

        This method handles the creation of a new Customer by validating the incoming data
        using the CustomerCreateSerializer, performing the creation, and sending a response
        with the created customer's data.

        Args:
            request (HttpRequest): The HTTP request object containing the data for creating a new customer.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            Response: A Response object containing the created customer's data and the HTTP status code.
        """
        # Initialize the serializer with the request data and context
        serializer = CustomerCreateSerializer(data=request.data, context=self.get_serializer_context())

        # Validate the serializer data, raising an exception if invalid
        serializer.is_valid(raise_exception=True)

        # Perform the creation of the customer, optionally sending an email if specified
        self.perform_create(serializer, send_email=serializer.validated_data.pop('send_email', False))

        # Get the headers for the success response
        headers = self.get_success_headers(serializer.data)

        # Return the response with the created customer's data and HTTP 201 status
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @transaction.atomic()
    def perform_update(self, serializer):
        """
        Update a customer info.
        @param serializer: serializer instance
        @return: customer instance
        """
        customer_inst = serializer.save(organizer=self.request.organizer)
        serializer.instance.log_action(
            'eventyay.customer.changed',
            user=self.request.user,
            auth=self.request.auth,
            data=self.request.data,
        )
        return customer_inst

    @action(detail=True, methods=["POST"])
    @transaction.atomic()
    def anonymize(self, request, **kwargs):
        """
        Anonymize a customer.
        @param request: request instance
        @param kwargs: arguments
        @return: result response
        """
        customer_obj = self.get_object()
        customer_obj.anonymize_customer()
        customer_obj.log_action(
            'eventyay.customer.anonymized',
            user=self.request.user,
            auth=self.request.auth
        )
        return Response(CustomerSerializer(customer_obj).data, status=status.HTTP_200_OK)
