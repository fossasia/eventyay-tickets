import datetime
import os

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.files.uploadedfile import UploadedFile
from django.forms.utils import from_current_timezone
from django.urls import reverse
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from ...base.forms import I18nModelForm

# Import for backwards compatibility with old import paths
from ...base.forms.widgets import (  # noqa
    DatePickerWidget,
    SplitDateTimePickerWidget,
    TimePickerWidget,
)


class TolerantFormsetModelForm(I18nModelForm):
    """
    This is equivalent to a normal I18nModelForm, but works around a problem that
    arises when the form is used inside a FormSet with can_order=True and django-formset-js
    enabled. In this configuration, even empty "extra" forms might have an ORDER value
    sent and Django marks the form as empty and raises validation errors because the other
    fields have not been filled.
    """

    def has_changed(self) -> bool:
        """
        Returns True if data differs from initial. Contrary to the default
        implementation, the ORDER field is being ignored.
        """
        for name, field in self.fields.items():
            if name == 'ORDER' or name == 'id':
                continue
            prefixed_name = self.add_prefix(name)
            data_value = field.widget.value_from_datadict(self.data, self.files, prefixed_name)
            if not field.show_hidden_initial:
                initial_value = self.initial.get(name, field.initial)
                if callable(initial_value):
                    initial_value = initial_value()
            else:
                initial_prefixed_name = self.add_initial_prefix(name)
                hidden_widget = field.hidden_widget()
                try:
                    initial_value = field.to_python(
                        hidden_widget.value_from_datadict(self.data, self.files, initial_prefixed_name)
                    )
                except forms.ValidationError:
                    # Always assume data has changed if validation fails.
                    self._changed_data.append(name)
                    continue
            # We're using a private API of Django here. This is not nice, but no problem as it seems
            # like this will become a public API in future Django.
            if field._has_changed(initial_value, data_value):
                return True
        return False


def selector(values, prop):
    # Given an iterable of PropertyValue objects, this will return a
    # list of their primary keys, ordered by the primary keys of the
    # properties they belong to EXCEPT the value for the property prop2.
    # We'll see later why we need this.
    return [v.id for v in sorted(values, key=lambda v: v.prop.id) if v.prop.id != prop.id]


class ClearableBasenameFileInput(forms.ClearableFileInput):
    template_name = 'pretixbase/forms/widgets/thumbnailed_file_input.html'

    class FakeFile(File):
        def __init__(self, file):
            self.file = file

        @property
        def name(self):
            if hasattr(self.file, 'display_name'):
                return self.file.display_name
            return self.file.name

        @property
        def is_img(self):
            return any(self.file.name.lower().endswith(e) for e in ('.jpg', '.jpeg', '.png', '.gif'))

        def __str__(self):
            if hasattr(self.file, 'display_name'):
                return self.file.display_name
            return os.path.basename(self.file.name).split('.', 1)[-1]

        @property
        def url(self):
            return self.file.url

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        ctx['widget']['value'] = self.FakeFile(value)
        ctx['widget']['cachedfile'] = None
        return ctx


class CachedFileInput(forms.ClearableFileInput):
    template_name = 'pretixbase/forms/widgets/thumbnailed_file_input.html'

    class FakeFile(File):
        def __init__(self, file):
            self.file = file

        @property
        def name(self):
            return self.file.filename

        @property
        def is_img(self):
            return any(self.file.filename.lower().endswith(e) for e in ('.jpg', '.jpeg', '.png', '.gif'))

        def __str__(self):
            return self.file.filename

        @property
        def url(self):
            return reverse('cachedfile.download', kwargs={'id': self.file.id})

    def value_from_datadict(self, data, files, name):
        from ...base.models import CachedFile

        v = super().value_from_datadict(data, files, name)
        if v is None and data.get(name + '-cachedfile'):  # An explicit "[x] clear" would be False, not None
            return CachedFile.objects.filter(id=data[name + '-cachedfile']).first()
        return v

    def get_context(self, name, value, attrs):
        from ...base.models import CachedFile

        if isinstance(value, CachedFile):
            value = self.FakeFile(value)

        ctx = super().get_context(name, value, attrs)
        ctx['widget']['value'] = value
        ctx['widget']['cachedfile'] = value.file if isinstance(value, self.FakeFile) else None
        ctx['widget']['hidden_name'] = name + '-cachedfile'
        return ctx


class SizeFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        self.max_size = kwargs.pop('max_size', None)
        super().__init__(*args, **kwargs)

    @staticmethod
    def _sizeof_fmt(num, suffix='B'):
        for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
            if abs(num) < 1024.0:
                return '%3.1f%s%s' % (num, unit, suffix)
            num /= 1024.0
        return '%.1f%s%s' % (num, 'Yi', suffix)

    def clean(self, *args, **kwargs):
        data = super().clean(*args, **kwargs)
        if isinstance(data, UploadedFile) and self.max_size and data.size > self.max_size:
            raise forms.ValidationError(
                _('Please do not upload files larger than {size}!').format(
                    size=SizeFileField._sizeof_fmt(self.max_size)
                )
            )
        return data


class ExtFileField(SizeFileField):
    widget = ClearableBasenameFileInput

    def __init__(self, *args, **kwargs):
        ext_whitelist = kwargs.pop('ext_whitelist')
        self.ext_whitelist = [i.lower() for i in ext_whitelist]
        super().__init__(*args, **kwargs)

    def clean(self, *args, **kwargs):
        data = super().clean(*args, **kwargs)
        if isinstance(data, File):
            filename = data.name
            ext = os.path.splitext(filename)[1]
            ext = ext.lower()
            if ext not in self.ext_whitelist:
                raise forms.ValidationError(_('Filetype not allowed!'))
        return data


class CachedFileField(ExtFileField):
    widget = CachedFileInput

    def to_python(self, data):
        from ...base.models import CachedFile

        if isinstance(data, CachedFile):
            return data

        return super().to_python(data)

    def bound_data(self, data, initial):
        from ...base.models import CachedFile

        if isinstance(data, File):
            if hasattr(data, '_uploaded_to'):
                return data._uploaded_to
            cf = CachedFile.objects.create(
                expires=now() + datetime.timedelta(days=1),
                date=now(),
                web_download=True,
                filename=data.name,
                type=data.content_type,
            )
            cf.file.save(data.name, data.file)
            cf.save()
            data._uploaded_to = cf
            return cf
        return super().bound_data(data, initial)

    def clean(self, *args, **kwargs):
        from ...base.models import CachedFile

        data = super().clean(*args, **kwargs)
        if isinstance(data, File):
            if hasattr(data, '_uploaded_to'):
                return data._uploaded_to
            cf = CachedFile.objects.create(
                expires=now() + datetime.timedelta(days=1),
                web_download=True,
                date=now(),
                filename=data.name,
                type=data.content_type,
            )
            cf.file.save(data.name, data.file)
            cf.save()
            data._uploaded_to = cf
            return cf
        return data


class SlugWidget(forms.TextInput):
    template_name = 'pretixcontrol/slug_widget.html'
    prefix = ''

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        ctx['pre'] = self.prefix
        return ctx


class MultipleLanguagesWidget(forms.CheckboxSelectMultiple):
    option_template_name = 'pretixcontrol/multi_languages_widget.html'

    def sort(self):
        self.choices = sorted(
            self.choices,
            key=lambda l: (
                (0 if l[0] in settings.LANGUAGES_OFFICIAL else (1 if l[0] not in settings.LANGUAGES_INCUBATING else 2)),
                str(l[1]),
            ),
        )

    def options(self, name, value, attrs=None):
        self.sort()
        return super().options(name, value, attrs)

    def optgroups(self, name, value, attrs=None):
        self.sort()
        return super().optgroups(name, value, attrs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        opt = super().create_option(name, value, label, selected, index, subindex, attrs)
        opt['official'] = value in settings.LANGUAGES_OFFICIAL
        opt['incubating'] = value in settings.LANGUAGES_INCUBATING
        return opt


class SingleLanguageWidget(forms.Select):
    def modify(self):
        if hasattr(self, '_modified'):
            return self.choices
        self.choices = sorted(
            self.choices,
            key=lambda l: (
                (0 if l[0] in settings.LANGUAGES_OFFICIAL else (1 if l[0] not in settings.LANGUAGES_INCUBATING else 2)),
                str(l[1]),
            ),
        )
        new_choices = []
        for k, v in self.choices:
            new_choices.append(
                (
                    k,
                    v
                    if k in settings.LANGUAGES_OFFICIAL
                    else (
                        '{} (inofficial translation)'.format(v)
                        if k not in settings.LANGUAGES_INCUBATING
                        else '{} (translation in progress)'.format(v)
                    ),
                )
            )
        self._modified = True
        self.choices = new_choices

    def options(self, name, value, attrs=None):
        self.modify()
        return super().options(name, value, attrs)

    def optgroups(self, name, value, attrs=None):
        self.modify()
        return super().optgroups(name, value, attrs)


class SplitDateTimeField(forms.SplitDateTimeField):
    def compress(self, data_list):
        # Differs from the default implementation: If only a time is given and no date, we consider the field empty
        if data_list:
            if data_list[0] in self.empty_values:
                return None
            if data_list[1] in self.empty_values:
                raise ValidationError(self.error_messages['invalid_date'], code='invalid_date')
            result = datetime.datetime.combine(*data_list)
            return from_current_timezone(result)
        return None


class FontSelect(forms.RadioSelect):
    option_template_name = 'pretixcontrol/font_option.html'
