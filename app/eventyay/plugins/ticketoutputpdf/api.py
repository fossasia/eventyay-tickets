from rest_framework import viewsets

from eventyay.api.serializers.i18n import I18nAwareModelSerializer
from eventyay.api.serializers.order import CompatibleJSONField

from .models import TicketLayout, TicketLayoutProduct


class ProductAssignmentSerializer(I18nAwareModelSerializer):
    class Meta:
        model = TicketLayoutProduct
        fields = ('id', 'layout', 'item', 'sales_channel')


class NestedProductAssignmentSerializer(I18nAwareModelSerializer):
    class Meta:
        model = TicketLayoutProduct
        fields = ('item', 'sales_channel')


class TicketLayoutSerializer(I18nAwareModelSerializer):
    layout = CompatibleJSONField()
    item_assignments = NestedProductAssignmentSerializer(many=True)

    class Meta:
        model = TicketLayout
        fields = ('id', 'name', 'default', 'layout', 'background', 'item_assignments')


class TicketLayoutViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TicketLayoutSerializer
    queryset = TicketLayout.objects.none()
    lookup_field = 'id'

    def get_queryset(self):
        return self.request.event.ticket_layouts.all()


class TicketLayoutProductViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProductAssignmentSerializer
    queryset = TicketLayoutProduct.objects.none()
    lookup_field = 'id'

    def get_queryset(self):
        return TicketLayoutProduct.objects.filter(item__event=self.request.event)
