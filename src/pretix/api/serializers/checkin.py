from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.db.models import Q

from pretix.api.serializers.event import SubEventSerializer
from pretix.api.serializers.i18n import I18nAwareModelSerializer
from pretix.base.channels import get_all_sales_channels
from pretix.base.models import Checkin, CheckinList


class CheckinListSerializer(I18nAwareModelSerializer):
    checkin_count = serializers.IntegerField(read_only=True)
    position_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CheckinList
        fields = (
            'id',
            'name',
            'all_products',
            'limit_products',
            'subevent',
            'checkin_count',
            'position_count',
            'include_pending',
            'auto_checkin_sales_channels',
            'allow_multiple_entries',
            'allow_entry_after_exit',
            'rules',
            'exit_all_at',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if 'subevent' in self.context['request'].query_params.getlist('expand'):
            self.fields['subevent'] = SubEventSerializer(read_only=True)

        for exclude_field in self.context['request'].query_params.getlist('exclude'):
            p = exclude_field.split('.')
            if p[0] in self.fields:
                if len(p) == 1:
                    del self.fields[p[0]]
                elif len(p) == 2:
                    self.fields[p[0]].child.fields.pop(p[1])

    def validate(self, data):
        data = super().validate(data)
        event = self.context['event']

        full_data = self.to_internal_value(self.to_representation(self.instance)) if self.instance else {}
        full_data.update(data)

        for item in full_data.get('limit_products'):
            if event != item.event:
                raise ValidationError(_('One or more items do not belong to this event.'))

        if event.has_subevents:
            if full_data.get('subevent') and event != full_data.get('subevent').event:
                raise ValidationError(_('The subevent does not belong to this event.'))
        else:
            if full_data.get('subevent'):
                raise ValidationError(_('The subevent does not belong to this event.'))

        for channel in full_data.get('auto_checkin_sales_channels') or []:
            if channel not in get_all_sales_channels():
                raise ValidationError(_('Unknown sales channel.'))

        CheckinList.validate_rules(data.get('rules'))

        return data


class CheckinRedeemInputSerializer(serializers.Serializer):
    lists = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        allow_empty=False
    )
    secret = serializers.CharField(required=True, allow_null=False)
    force = serializers.BooleanField(default=False, required=False)
    source_type = serializers.ChoiceField(choices=['barcode'], default='barcode')
    type = serializers.ChoiceField(choices=Checkin.CHECKIN_TYPES, default=Checkin.TYPE_ENTRY)
    ignore_unpaid = serializers.BooleanField(default=False, required=False)
    questions_supported = serializers.BooleanField(default=True, required=False)
    nonce = serializers.CharField(required=False, allow_null=True)
    datetime = serializers.DateTimeField(required=False, allow_null=True)
    answers = serializers.JSONField(required=False, allow_null=True)
    
    def validate_lists(self, value):
        """Custom validation for checkin lists that handles scope properly"""
        from django_scopes import scope
        
        events = self.context.get('events', [])
        if not events:
            raise serializers.ValidationError("No events available in context")
        
        # Get the organizer from the first event
        organizer = events[0].organizer
        
        # Validate within the proper scope
        with scope(organizer=organizer):
            # Get available checkin lists for the events
            available_lists = CheckinList.objects.filter(
                event__in=events
            ).select_related('event')
            
            available_ids = set(available_lists.values_list('id', flat=True))
            
            # Validate each list ID
            validated_lists = []
            for list_id in value:
                if list_id not in available_ids:
                    raise serializers.ValidationError(
                        f'Invalid pk "{list_id}" - object does not exist.'
                    )
                validated_lists.append(
                    available_lists.get(id=list_id)
                )
            
            return validated_lists


class MiniCheckinListSerializer(I18nAwareModelSerializer):
    event = serializers.SlugRelatedField(slug_field='slug', read_only=True)
    subevent = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = CheckinList
        fields = ('id', 'name', 'event', 'subevent', 'include_pending')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
