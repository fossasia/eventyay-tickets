from django.core.exceptions import ValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from pretalx.common.models import CachedFile


@extend_schema_field(
    {
        "type": "str",
        "description": 'When reading data, a URL pointing to a downloadable file. When writing adata, a reference to a file uploaded via the <a href="https://docs.pretalx.org/api/fundamentals/#file-uploads">file uploads endpoint</a>.',
    }
)
class UploadedFileField(serializers.Field):
    default_error_messages = {
        "required": "No file was submitted.",
        "not_found": "The submitted file ID was not found.",
        "invalid_type": "The submitted file has a file type that is not allowed in this field.",
        "size": "The submitted file is too large to be used in this field.",
    }

    def __init__(self, *args, **kwargs):
        self.allowed_types = kwargs.pop("allowed_types", None)
        self.max_size = kwargs.pop("max_size", None)
        super().__init__(*args, **kwargs)

    def to_internal_value(self, data):
        request = self.context.get("request", None)
        try:
            cf = CachedFile.objects.get(
                session_key=f"api-upload-{request.auth.token}",
                file__isnull=False,
                pk=data[len("file:") :],
            )
        except (
            ValidationError,
            IndexError,
            CachedFile.DoesNotExist,
        ):  # pragma: no cover
            self.fail("not_found")

        if self.allowed_types and cf.type not in self.allowed_types:
            self.fail("invalid_type")  # pragma: no cover
        if self.max_size and cf.file.size > self.max_size:
            self.fail("size")  # pragma: no cover

        return cf.file

    def to_representation(self, value):
        if not value:
            return None

        try:
            url = value.url
            request = self.context["request"]
        except (AttributeError, KeyError):  # pragma: no cover
            return None
        return request.build_absolute_uri(url)
