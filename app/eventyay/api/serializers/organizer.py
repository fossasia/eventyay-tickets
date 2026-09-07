import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from eventyay.api.serializers.i18n import I18nAwareModelSerializer
from eventyay.api.serializers.order import CompatibleJSONField
from eventyay.api.serializers.settings import SettingsSerializer
from eventyay.base.auth import get_auth_backends
from eventyay.base.entitlements import check_entitlement
from eventyay.base.i18n import get_language_without_region
from eventyay.base.models import (
    Device,
    GiftCard,
    GiftCardTransaction,
    Organizer,
    OrganizerFollower,
    SeatingPlan,
    Team,
    TeamAPIToken,
    TeamInvite,
    User,
)
from eventyay.base.models.seating import SeatingPlanLayoutValidator
from eventyay.base.models.track import Track
from eventyay.base.services.mail import SendMailException, mail
from eventyay.base.services.teams import send_team_invitation_email
from eventyay.base.settings import validate_organizer_settings
from eventyay.helpers.urls import build_absolute_uri


logger = logging.getLogger(__name__)


class OrganizerSerializer(I18nAwareModelSerializer):
    follower_count = serializers.SerializerMethodField(
        help_text=(
            'Number of users following this organizer, or null when follower counts '
            'are hidden by the organizer.'
        ),
    )
    is_following = serializers.SerializerMethodField(
        help_text='Whether the currently authenticated user is following this organizer.',
    )
    is_default = serializers.SerializerMethodField(
        help_text='Whether this organizer is the default organizer for the currently authenticated user.',
    )

    class Meta:
        model = Organizer
        fields = ('name', 'slug', 'follower_count', 'is_following', 'is_default')

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_follower_count(self, obj):
        if not obj.settings.get('community_show_follower_count', as_type=bool, default=True):
            return None
        if hasattr(obj, '_follower_count'):
            return obj._follower_count
        return OrganizerFollower.objects.filter(organizer=obj).count()

    @extend_schema_field(serializers.BooleanField())
    def get_is_following(self, obj):
        if hasattr(obj, '_is_following'):
            return obj._is_following
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            return OrganizerFollower.objects.filter(organizer=obj, user=request.user).exists()
        return False

    @extend_schema_field(serializers.BooleanField())
    def get_is_default(self, obj):
        request = self.context.get('request')
        if not (request and request.user and request.user.is_authenticated):
            return False
        if not hasattr(request.user, '_cached_default_organizer_id'):
            default_org = request.user.get_default_organizer()
            request.user._cached_default_organizer_id = default_org.id if default_org else None
        return request.user._cached_default_organizer_id == obj.id


class OrganizerFollowResponseSerializer(serializers.Serializer):
    following = serializers.BooleanField(read_only=True)
    created = serializers.BooleanField(read_only=True)


class OrganizerUnfollowResponseSerializer(serializers.Serializer):
    following = serializers.BooleanField(read_only=True)
    deleted = serializers.BooleanField(read_only=True)


class OrganizerSetDefaultResponseSerializer(serializers.Serializer):
    status = serializers.CharField(read_only=True)
    default_organizer = serializers.CharField(read_only=True)


class OrganizerFollowersResponseSerializer(serializers.Serializer):
    follower_count = serializers.IntegerField(allow_null=True, read_only=True)
    is_following = serializers.BooleanField(read_only=True)


class OrganizerErrorResponseSerializer(serializers.Serializer):
    detail = serializers.CharField(read_only=True)


class SeatingPlanSerializer(I18nAwareModelSerializer):
    layout = CompatibleJSONField(validators=[SeatingPlanLayoutValidator()])

    class Meta:
        model = SeatingPlan
        fields = ('id', 'name', 'layout')


class GiftCardSerializer(I18nAwareModelSerializer):
    value = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.00'))

    def validate(self, data):
        data = super().validate(data)
        s = data['secret']
        qs = GiftCard.objects.filter(secret=s).filter(
            Q(issuer=self.context['organizer'])
            | Q(issuer__gift_card_collector_acceptance__collector=self.context['organizer'])
        )
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(
                {
                    'secret': _(
                        'A gift card with the same secret already exists in your or an affiliated organizer account.'
                    )
                }
            )
        return data

    class Meta:
        model = GiftCard
        fields = (
            'id',
            'secret',
            'issuance',
            'value',
            'currency',
            'testmode',
            'expires',
            'conditions',
        )


class OrderEventSlugField(serializers.RelatedField):
    def to_representation(self, obj):
        return obj.event.slug


class GiftCardTransactionSerializer(I18nAwareModelSerializer):
    order = serializers.SlugRelatedField(slug_field='code', read_only=True)
    event = OrderEventSlugField(source='order', read_only=True)

    class Meta:
        model = GiftCardTransaction
        fields = ('id', 'datetime', 'value', 'event', 'order', 'text')


class EventSlugField(serializers.SlugRelatedField):
    def get_queryset(self):
        return self.context['organizer'].events.all()


class TeamSerializer(serializers.ModelSerializer):
    limit_events = EventSlugField(slug_field='slug', many=True)
    limit_tracks = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Track.objects.none(),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        organizer = self.context.get('organizer')
        if organizer is not None:
            self.fields['limit_tracks'].queryset = Track.objects.filter(event__organizer=organizer)

    class Meta:
        model = Team
        fields = (
            'id',
            'name',
            'all_events',
            'limit_events',
            'limit_tracks',
            'can_create_events',
            'can_change_teams',
            'can_change_organizer_settings',
            'can_manage_gift_cards',
            'can_change_event_settings',
            'can_change_config',
            'can_change_items',
            'can_view_orders',
            'can_change_orders',
            'can_manage_bank_transfers',
            'can_view_vouchers',
            'can_change_vouchers',
            'can_checkin_orders',
            'can_change_submissions',
            'is_reviewer',
            'force_hide_speaker_names',
            'can_change_exhibition_proposals',
            'is_exhibition_reviewer',
            'hide_exhibition_applicant_emails',
            'can_manage_social_media',
            'force_hide_speaker_emails',
            'can_video_manage_content',
            'can_video_moderate',
            'can_video_manage_kiosks',
            'can_video_view_analytics',
        )

    def validate(self, data):
        full_data = self.to_internal_value(self.to_representation(self.instance)) if self.instance else {}
        full_data.update(data)
        if full_data.get('limit_events') and full_data.get('all_events'):
            raise ValidationError('Do not set both limit_events and all_events.')
        for source, implied_permissions in Team.PERMISSION_IMPLICATIONS.items():
            if full_data.get(source):
                for implied in implied_permissions:
                    data[implied] = True
        return data


class DeviceSerializer(serializers.ModelSerializer):
    limit_events = EventSlugField(slug_field='slug', many=True)
    limit_checkin_lists = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    device_id = serializers.IntegerField(read_only=True)
    unique_serial = serializers.CharField(read_only=True)
    hardware_brand = serializers.CharField(read_only=True)
    hardware_model = serializers.CharField(read_only=True)
    software_brand = serializers.CharField(read_only=True)
    software_version = serializers.CharField(read_only=True)
    created = serializers.DateTimeField(read_only=True)
    revoked = serializers.BooleanField(read_only=True)
    initialized = serializers.DateTimeField(read_only=True)
    initialization_token = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Device
        fields = (
            'device_id',
            'unique_serial',
            'initialization_token',
            'all_events',
            'limit_events',
            'revoked',
            'name',
            'created',
            'initialized',
            'hardware_brand',
            'hardware_model',
            'software_brand',
            'software_version',
            'security_profile',
            'limit_checkin_lists',
        )


class TeamInviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamInvite
        fields = ('id', 'email')

    def _send_invite(self, instance):
        try:
            mail(
                instance.email,
                _('eventyay account invitation'),
                'pretixcontrol/email/invitation.txt',
                {
                    'user': self,
                    'organizer': self.context['organizer'].name,
                    'team': instance.team.name,
                    'url': build_absolute_uri('control:auth.invite', kwargs={'token': instance.token}),
                },
                event=None,
                locale=get_language_without_region(),  # TODO: expose?
            )
        except SendMailException:
            pass  # Already logged

    def _check_full_admin_limit(self, email, user=None):
        """Enforce full-admin entitlement before adding a member or invite."""
        from eventyay.base.services.teams import check_full_admin_limit
        decision = check_full_admin_limit(self.context['team'], email=email, user=user)
        if not decision.allowed:
            raise ValidationError(decision.message)

    def create(self, validated_data):
        if 'email' in validated_data:
            try:
                user = User.objects.get(email__iexact=validated_data['email'])
            except User.DoesNotExist:
                if self.context['team'].invites.filter(email__iexact=validated_data['email']).exists():
                    raise ValidationError(_('This user already has been invited for this team.'))
                if 'native' not in get_auth_backends():
                    raise ValidationError('Users need to have a eventyay account before they can be invited.')

                self._check_full_admin_limit(validated_data['email'])

                invite = self.context['team'].invites.create(email=validated_data['email'])
                transaction.on_commit(lambda: self._send_invite(invite))
                invite.team.log_action(
                    'eventyay.team.invite.created',
                    data={'email': validated_data['email']},
                    **self.context['log_kwargs'],
                )
                return invite
            else:
                if self.context['team'].members.filter(pk=user.pk).exists():
                    raise ValidationError(_('This user already has permissions for this team.'))

                self._check_full_admin_limit(validated_data['email'], user=user)

                self.context['team'].members.add(user)

                self.context['team'].log_action(
                    'eventyay.team.member.added',
                    data={
                        'email': user.email,
                        'user': user.pk,
                    },
                    **self.context['log_kwargs'],
                )

                transaction.on_commit(lambda: send_team_invitation_email(
                    user=user,
                    organizer_name=self.context['organizer'].name,
                    team_name=self.context['team'].name,
                    url=build_absolute_uri(
                        'eventyay_common:organizer.team',
                        kwargs={
                            'organizer': self.context['organizer'].slug,
                            'team': self.context['team'].pk,
                        },
                    ),
                    locale=get_language_without_region(),
                    is_registered_user=True,
                ))

                return TeamInvite(email=user.email)
        else:
            raise ValidationError('No email address given.')


class TeamAPITokenSerializer(serializers.ModelSerializer):
    active = serializers.BooleanField(default=True, read_only=True)

    class Meta:
        model = TeamAPIToken
        fields = ('id', 'name', 'active')


class TeamMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'fullname', 'require_2fa')


class OrganizerSettingsSerializer(SettingsSerializer):
    default_fields = [
        'contact_mail',
        'imprint_url',
        'organizer_info_text',
        'event_list_type',
        'event_list_availability',
        'organizer_homepage_text',
        'organizer_link_back',
        'organizer_header_image',
        'organizer_header_image_large',
        'community_follow_enabled',
        'community_show_follower_count',
        'giftcard_length',
        'giftcard_expiry_years',
        'locales',
        'region',
        'event_team_provisioning',
        'header_background_color',
        'header_text_color',
        'navigation_text_color',
        'menu_text_scroll_over_color',
        'primary_color',
        'theme_color_success',
        'theme_color_danger',
        'theme_color_background',
        'hover_button_color',
        'video_navigation_background_color',
        'video_sidebar_text_color',
        'video_sidebar_hover_color',
        'theme_round_borders',
        'primary_font',
        'organizer_logo_image',
        'privacy_policy',
    ]

    def __init__(self, *args, **kwargs):
        self.organizer = kwargs.pop('organizer')
        super().__init__(*args, **kwargs)

    def validate(self, data):
        data = super().validate(data)
        settings_dict = self.instance.freeze()
        settings_dict.update(data)
        validate_organizer_settings(self.organizer, settings_dict)
        return data

    def get_new_filename(self, name: str) -> str:
        nonce = get_random_string(length=8)
        fname = '%s/%s.%s.%s' % (
            self.organizer.slug,
            name.split('/')[-1],
            nonce,
            name.split('.')[-1],
        )
        # TODO: make sure pub is always correct
        return 'pub/' + fname
