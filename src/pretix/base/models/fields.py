from django.core import exceptions
from django.db.models import TextField, lookups as builtin_lookups
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

DELIMITER = "\x1F"


class MultiStringField(TextField):
    default_error_messages = {
        'delimiter_found': _('No value can contain the delimiter character.')
    }

    def __init__(self, verbose_name=None, name=None, delimiter=DELIMITER, **kwargs):
        self.delimiter = delimiter
        super().__init__(verbose_name, name, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        return name, path, args, kwargs

    def to_python(self, value):
        if isinstance(value, (list, tuple)):
            return value
        elif value:
            return [v for v in value.split(self.delimiter) if v]
        else:
            return []

    def get_prep_value(self, value):
        if isinstance(value, (list, tuple)):
            return self.delimiter + self.delimiter.join(value) + self.delimiter
        elif value is None:
            return ""
        raise TypeError("Invalid data type passed.")

    def get_prep_lookup(self, lookup_type, value):  # NOQA
        raise TypeError('Lookups on multi strings are currently not supported.')

    def from_db_value(self, value, expression, connection):
        if value:
            return [v for v in value.split(self.delimiter) if v]
        else:
            return []

    def validate(self, value, model_instance):
        super().validate(value, model_instance)
        for l in value:
            if self.delimiter in l:
                raise exceptions.ValidationError(
                    self.error_messages['delimiter_found'],
                    code='delimiter_found',
                )

    def get_lookup(self, lookup_name):
        if lookup_name == 'contains':
            return make_multi_string_contains_lookup(self.delimiter)
        elif lookup_name == 'icontains':
            return make_multi_string_icontains_lookup(self.delimiter)
        raise NotImplementedError(
            "Lookup '{}' doesn't work with MultiStringField".format(lookup_name),
        )


def make_multi_string_contains_lookup(delimiter):
    class Cls(builtin_lookups.Contains):
        def process_rhs(self, qn, connection):
            sql, params = super().process_rhs(qn, connection)
            params[0] = "%" + delimiter + params[0][1:-1] + delimiter + "%"
            return sql, params
    return Cls


def make_multi_string_icontains_lookup(delimiter):
    class Cls(builtin_lookups.IContains):
        def process_rhs(self, qn, connection):
            sql, params = super().process_rhs(qn, connection)
            params[0] = "%" + delimiter + params[0][1:-1] + delimiter + "%"
            return sql, params
    return Cls


class MultiStringSerializer(serializers.Field):
    def __init__(self, **kwargs):
        self.allow_blank = kwargs.pop('allow_blank', False)
        super().__init__(**kwargs)

    def to_representation(self, value):
        return value

    def to_internal_value(self, data):
        if isinstance(data, list):
            return data
        else:
            raise ValidationError('Invalid data type.')


serializers.ModelSerializer.serializer_field_mapping[MultiStringField] = MultiStringSerializer
