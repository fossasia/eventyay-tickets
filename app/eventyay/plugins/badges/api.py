import base64

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from eventyay.api.serializers.i18n import I18nAwareModelSerializer
from eventyay.api.serializers.order import CompatibleJSONField
from eventyay.base.models import CachedFile, OrderPosition
from eventyay.base.services.tickets import generate_orderposition

from .apps import PDFRenderer
from .models import BadgeProduct, BadgeLayout


class BadgeProductAssignmentSerializer(I18nAwareModelSerializer):
    class Meta:
        model = BadgeProduct
        fields = ('id', 'product', 'layout')


class NestedProductAssignmentSerializer(I18nAwareModelSerializer):
    class Meta:
        model = BadgeProduct
        fields = ('product',)


class BadgeLayoutSerializer(I18nAwareModelSerializer):
    layout = CompatibleJSONField()
    product_assignments = NestedProductAssignmentSerializer(many=True)
    size = CompatibleJSONField()

    class Meta:
        model = BadgeLayout
        fields = (
            'id',
            'name',
            'default',
            'layout',
            'size',
            'background',
            'product_assignments',
        )


class BadgeLayoutViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BadgeLayoutSerializer
    queryset = BadgeLayout.objects.none()
    lookup_field = 'id'

    def get_queryset(self):
        return self.request.event.badge_layouts.all()


class BadgeProductViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BadgeProductAssignmentSerializer
    queryset = BadgeProduct.objects.none()
    lookup_field = 'id'

    def get_queryset(self):
        return BadgeProduct.objects.filter(product__event=self.request.event)


class BadgePreviewView(APIView):
    renderer_classes = [PDFRenderer]

    def get(self, request, organizer, event, position):
        op = get_object_or_404(
            OrderPosition,
            order__event__slug=event,
            order__event__organizer__slug=organizer,
            pk=position,
        )

        # Check if badges plugin is enabled
        if 'eventyay.plugins.badges' not in op.order.event.plugins:
            return Response(
                {'error': 'Badges plugin is not enabled for this event'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generate the badge preview
        from .providers import BadgeOutputProvider

        provider = BadgeOutputProvider(op.order.event)

        try:
            _, _, pdf_content = provider.generate(op)
            base64_pdf = base64.b64encode(pdf_content).decode('utf-8')
            response = Response({'pdf_base64': base64_pdf}, status=status.HTTP_200_OK)
            response['Access-Control-Allow-Credentials'] = 'true'
            return response
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BadgeDownloadView(APIView):
    renderer_classes = [PDFRenderer]

    def get(self, request, organizer, event, position):
        try:
            op = get_object_or_404(
                OrderPosition,
                order__event__slug=event,
                order__event__organizer__slug=organizer,
                pk=position,
            )

            # Check if badges plugin is enabled
            if 'eventyay.plugins.badges' not in op.order.event.plugins:
                return Response(
                    {'error': 'Badges plugin is not enabled for this event'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check if there's already a cached file
            cached_file = CachedFile.objects.filter(
                filename__startswith=f'badge_{position}_', expires__isnull=True
            ).last()

            if cached_file and cached_file.file:
                base64_pdf = base64.b64encode(cached_file.file.read()).decode('utf-8')
                return Response(
                    {
                        'filename': cached_file.filename,
                        'type': 'application/pdf',
                        'base64_pdf': base64_pdf,
                    }
                )

            # If no cached file exists, generate one
            from .providers import BadgeOutputProvider

            provider = BadgeOutputProvider(op.order.event)

            try:
                # Try to generate immediately
                filename, mimetype, pdf_content = provider.generate(op)

                # Cache the generated file
                base64_pdf = base64.b64encode(pdf_content).decode('utf-8')

                return Response(
                    {
                        'filename': filename,
                        'mimetype': mimetype,
                        'pdf_base64': base64_pdf,
                    }
                )

            except Exception:
                # If immediate generation fails, fall back to async generation
                generate_orderposition.apply_async(args=(op.pk, 'badge'))
                return Response(
                    {
                        'status': 'generating',
                        'message': 'Badge generation has been started. Please retry in a few seconds.',
                    },
                    status=status.HTTP_202_ACCEPTED,
                )

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
