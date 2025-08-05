import datetime

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.timezone import now
from drf_spectacular.utils import (
    OpenApiExample,
    extend_schema,
    extend_schema_serializer,
)
from rest_framework import permissions, serializers
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FileUploadParser
from rest_framework.response import Response
from rest_framework.views import APIView

from pretalx.common.image import validate_image
from pretalx.common.models import CachedFile


@extend_schema_serializer(examples=[OpenApiExample("", value={"id": "file:1234-5678"})])
class FileResponseSerializer(serializers.Serializer):
    """Serializer for file upload response."""

    id = serializers.CharField(help_text="Cached file identifier")


class UploadView(APIView):
    parser_classes = [FileUploadParser]
    permission_classes = [permissions.IsAuthenticated]
    allowed_types = {
        "image/png": [".png"],
        "image/jpeg": [".jpg", ".jpeg"],
        "image/gif": [".gif"],
        "image/svg+xml": [".svg"],
        "application/pdf": [".pdf"],
    }

    @extend_schema(
        operation_id="File upload",
        description="Upload a file (image or PDF) for temporary storage. "
        "Allowed file types: PNG, JPEG, GIF, SVG, PDF.",
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "format": "binary",
                    }
                },
            }
        },
        responses={
            201: FileResponseSerializer,
            400: {"type": "object", "description": "Validation error"},
        },
        tags=["file-uploads"],
    )
    def post(self, request):
        if "file" not in request.data:
            raise ValidationError("No file has been submitted.")
        file_obj = request.data["file"]
        content_type = file_obj.content_type.split(";")[0]  # ignore e.g. "; charset=…"
        if not (allowed_extensions := self.allowed_types.get(content_type)):
            raise ValidationError("Content type is not allowed.")
        if not any(file_obj.name.endswith(ext) for ext in allowed_extensions):
            raise ValidationError(
                'File name "{name}" has an invalid extension for type "{type}"'.format(
                    name=file_obj.name, type=content_type
                )
            )

        if content_type != "application/pdf":
            try:
                validate_image(file_obj)
            except DjangoValidationError as e:
                raise ValidationError(e.message)

        cf = CachedFile.objects.create(
            expires=now() + datetime.timedelta(days=1),
            timestamp=now(),
            filename=file_obj.name,
            content_type=content_type,
            session_key=f"api-upload-{request.auth.token}",
        )
        cf.file.save(file_obj.name, file_obj, save=False)
        cf.save(update_fields=("file",))
        return Response({"id": f"file:{cf.pk}"}, status=201)
