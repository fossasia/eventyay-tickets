import urllib
from contextlib import suppress
from importlib import import_module

from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db.models import CharField, Q
from django.db.models.functions import Lower
from django.http import Http404
from django.utils.functional import cached_property
from i18nfield.forms import I18nModelForm
from rules.contrib.views import PermissionRequiredMixin

from pretalx.common.forms import SearchForm

SessionStore = import_module(settings.SESSION_ENGINE).SessionStore


class ActionFromUrl:
    write_permission_required = None

    @cached_property
    def object(self):
        return self.get_object()

    @cached_property
    def permission_object(self):
        return self.object

    @cached_property
    def _action(self):
        if not any(_id in self.kwargs for _id in ['pk', 'code']):
            return 'create'
        if self.request.user.has_perm(
            self.write_permission_required, self.permission_object
        ):
            return 'edit'
        return 'view'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['action'] = self._action
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['read_only'] = self._action == 'view'
        if hasattr(self.request, 'event') and issubclass(
            self.form_class, I18nModelForm
        ):
            kwargs['locales'] = self.request.event.locales
        return kwargs


class Sortable:

    sortable_fields = []

    def sort_queryset(self, qs):
        sort_key = self.request.GET.get('sort') or getattr(
            self, 'default_sort_field', ''
        )
        if sort_key:
            plain_key = sort_key[1:] if sort_key.startswith('-') else sort_key
            reverse = not (plain_key == sort_key)
            if plain_key in self.sortable_fields:
                is_text = False
                if '__' not in plain_key:
                    with suppress(FieldDoesNotExist):
                        is_text = isinstance(
                            qs.model._meta.get_field(plain_key), CharField
                        )
                else:
                    split_key = plain_key.split('__')
                    if len(split_key) == 2:
                        is_text = isinstance(
                            qs.model._meta.get_field(
                                split_key[0]
                            ).related_model._meta.get_field(split_key[1]),
                            CharField,
                        )

                if is_text:
                    # TODO: this only sorts direct lookups case insensitively
                    # A sorting field like 'speaker__name' will not be found
                    qs = qs.annotate(key=Lower(plain_key)).order_by(
                        '-key' if reverse else 'key'
                    )
                else:
                    qs = qs.order_by(sort_key)
        return qs


class Filterable:

    filter_fields = []
    default_filters = []

    def filter_queryset(self, qs):
        if self.filter_fields:
            qs = self._handle_filter(qs)
        if 'q' in self.request.GET:
            qs = self._handle_search(qs)
        return qs

    def _handle_filter(self, qs):
        for key in self.request.GET:  # Do NOT use items() to preserve multivalue fields
            value = self.request.GET.getlist(key)
            if len(value) == 1:
                value = value[0]
            elif len(value) > 1:
                key = f'{key}__in' if not key.endswith('__in') else key
            if value:
                lookup_key = key.split('__')[0]
                print(value)
                if lookup_key in self.filter_fields:
                    qs = qs.filter(**{key: value})
        return qs

    def _handle_search(self, qs):
        query = urllib.parse.unquote(self.request.GET['q'])
        _filters = [Q(**{field: query}) for field in self.default_filters]
        if len(_filters) > 1:
            _filter = _filters[0]
            for additional_filter in _filters[1:]:
                _filter = _filter | additional_filter
            qs = qs.filter(_filter)
        elif _filters:
            qs = qs.filter(_filters[0])
        return qs

    def get_context_data(self, *args, **kwargs):
        from django import forms

        context = super().get_context_data(*args, **kwargs)
        context['search_form'] = SearchForm(
            self.request.GET if 'q' in self.request.GET else {}
        )
        if hasattr(self, 'filter_form_class'):
            context['filter_form'] = self.filter_form_class(
                self.request.event, self.request.GET
            )
        elif hasattr(self, 'get_filter_form'):
            context['filter_form'] = self.get_filter_form()
        elif self.filter_fields:
            context['filter_form'] = forms.modelform_factory(
                self.model, fields=self.filter_fields
            )(self.request.GET)
            for field in context['filter_form'].fields.values():
                field.required = False
                if hasattr(field, 'queryset'):
                    field.queryset = field.queryset.filter(event=self.request.event)
        return context


class PermissionRequired(PermissionRequiredMixin):
    def has_permission(self):
        result = super().has_permission()
        if not result:
            request = getattr(self, 'request', None)
            key = f'pretalx_event_access_{request.event.pk}'
            if request and hasattr(request, 'event') and key in request.session:
                sparent = SessionStore(request.session.get(key))
                parentdata = []
                with suppress(Exception):
                    parentdata = sparent.load()
                return 'event_access' in parentdata
        return result

    def get_login_url(self):
        """We do this to avoid leaking data about existing pages."""
        raise Http404()
