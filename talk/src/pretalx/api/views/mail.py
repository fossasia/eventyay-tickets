from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets

from pretalx.api.documentation import build_search_docs
from pretalx.api.mixins import PretalxViewSetMixin
from pretalx.api.serializers.mail import MailTemplateSerializer
from pretalx.mail.models import MailTemplate


@extend_schema_view(
    list=extend_schema(
        summary="List Mail Templates", parameters=[build_search_docs("role", "subject")]
    ),
    retrieve=extend_schema(summary="Show Mail Template"),
    create=extend_schema(summary="Create Mail Template"),
    update=extend_schema(summary="Update Mail Template"),
    partial_update=extend_schema(summary="Update Mail Template (Partial Update)"),
    destroy=extend_schema(summary="Delete Mail Template"),
)
class MailTemplateViewSet(PretalxViewSetMixin, viewsets.ModelViewSet):
    serializer_class = MailTemplateSerializer
    queryset = MailTemplate.objects.none()
    endpoint = "mail-templates"
    search_fields = ("role", "subject")

    def get_queryset(self):
        return self.event.mail_templates.all().select_related("event").order_by("pk")
