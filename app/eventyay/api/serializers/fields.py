import os
from collections import OrderedDict

from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.validators import URLValidator
from django.utils.translation import gettext_lazy as _
from hierarkey.proxy import HierarkeyProxy
from rest_framework import serializers

from eventyay.common.urls import get_file_url_path, get_url_scheme, is_http_url, normalize_url_scheme
from eventyay.helpers.image_optimize import optimize_uploaded_image


def remove_duplicates_from_list(data):
    return list(OrderedDict.fromkeys(data))


class ListMultipleChoiceField(serializers.MultipleChoiceField):
    def to_internal_value(self, data):
        if isinstance(data, str) or not hasattr(data, '__iter__'):
            self.fail('not_a_list', input_type=type(data).__name__)
        if not self.allow_empty and len(data) == 0:
            self.fail('empty')

        internal_value_data = [super(serializers.MultipleChoiceField, self).to_internal_value(item) for item in data]

        return remove_duplicates_from_list(internal_value_data)

    def to_representation(self, value):
        representation_data = [self.choice_strings_to_values.get(str(item), item) for item in value]

        return remove_duplicates_from_list(representation_data)


class UploadedFileField(serializers.Field):
    default_error_messages = {
        'required': 'No file was submitted.',
        'not_found': 'The submitted file ID was not found.',
        'invalid_type': 'The submitted file has a file type that is not allowed in this field.',
        'size': 'The submitted file is too large to be used in this field.',
        'invalid_image': 'Upload a valid image. The file you uploaded was either not an image or a corrupted image.',
    }

    def __init__(self, *args, **kwargs):
        self.allowed_types = kwargs.pop('allowed_types', None)
        self.max_size = kwargs.pop('max_size', None)
        super().__init__(*args, **kwargs)

    def to_internal_value(self, data):
        from eventyay.base.models import CachedFile

        request = self.context.get('request', None)
        try:
            cf = CachedFile.objects.get(
                session_key=f'api-upload-{str(type(request.user or request.auth))}-{(request.user or request.auth).pk}',
                file__isnull=False,
                pk=data[len('file:') :],
            )
        except (ValidationError, IndexError):  # invalid uuid
            self.fail('not_found')
        except CachedFile.DoesNotExist:
            self.fail('not_found')

        if self.allowed_types and cf.type not in self.allowed_types:
            self.fail('invalid_type')
        if self.max_size and cf.file.size > self.max_size:
            self.fail('size')

        if cf.type.startswith('image/') and self.field_name in [
            'picture', 'logo_image', 'event_logo_image', 'event_preview_image', 
            'og_image', 'organizer_logo_image', 'organizer_header_image', 
            'invoice_logo_image', 'startpage_header_image'
        ]:
            try:
                opt = optimize_uploaded_image(cf.file, self.field_name)
                orig_name = os.path.splitext(cf.file.name or 'upload')[0]
                opt.optimized.name = f'{orig_name}.{opt.optimized_ext}'
                return opt.optimized
            except (ValueError, OSError):
                self.fail('invalid_image')

        return cf.file

    def to_representation(self, value):
        if not value:
            return None

        try:
            url = value.url
        except AttributeError:
            return None
        request = self.context['request']
        return request.build_absolute_uri(url)


class UploadedFileOrURLField(UploadedFileField):
    default_error_messages = {
        **UploadedFileField.default_error_messages,
        'invalid_url': 'Enter a valid URL.',
    }

    def get_attribute(self, instance):
        if isinstance(instance, HierarkeyProxy):
            return instance.get(self.source_attrs[-1], as_type=str, default=None)
        return super().get_attribute(instance)

    def to_internal_value(self, data):
        if isinstance(data, str):
            if is_http_url(data):
                data = normalize_url_scheme(data)
                try:
                    URLValidator(schemes=['http', 'https'])(data)
                except ValidationError:
                    self.fail('invalid_url')
                return data
            if get_url_scheme(data) and not data.startswith('file:'):
                self.fail('invalid_url')
        return super().to_internal_value(data)

    def to_representation(self, value):
        if not value:
            return None
        if isinstance(value, str):
            if is_http_url(value):
                return value
            file_path = get_file_url_path(value)
            if file_path:
                url = default_storage.url(file_path)
                request = self.context.get('request')
                return request.build_absolute_uri(url) if request else url
        return super().to_representation(value)


class UploadedFileNoNewURLField(UploadedFileOrURLField):
    default_error_messages = {
        **UploadedFileOrURLField.default_error_messages,
        'url_not_allowed': _('External image URLs are no longer accepted. Please upload a file instead.'),
    }

    def to_internal_value(self, data):
        if isinstance(data, str):
            if is_http_url(data):
                self.fail('url_not_allowed')
            scheme = (get_url_scheme(data) or '').lower()
            # Allow file: strings — they are internal upload references (file:<uuid>)
            # produced by the /api/v1/upload endpoint and must reach UploadedFileField.
            # All other URL schemes (ftp, javascript, data, etc.) are rejected.
            # We call UploadedFileField.to_internal_value directly (skipping
            # UploadedFileOrURLField) because that parent would re-accept HTTP URLs.
            if scheme and scheme != 'file':
                self.fail('url_not_allowed')
        return UploadedFileField.to_internal_value(self, data)
