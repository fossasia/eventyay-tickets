import urllib
from contextlib import suppress

from django.core.exceptions import FieldDoesNotExist
from django.db.models import CharField, Q
from django.db.models.functions import Lower
from django.views.generic.detail import SingleObjectTemplateResponseMixin
from django.views.generic.edit import ModelFormMixin, ProcessFormView
from i18nfield.forms import I18nModelForm

from pretalx.common.forms import SearchForm


class ActionFromUrl:
    @property
    def _action(self):
        return self.request.resolver_match.url_name.split('.')[-1]

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['action'] = self._action
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['read_only'] = (self._action == 'view')
        if hasattr(self.request, 'event') and issubclass(self.form_class, I18nModelForm):
            kwargs['locales'] = self.request.event.locales
        return kwargs


class CreateOrUpdateView(SingleObjectTemplateResponseMixin, ModelFormMixin, ProcessFormView):

    def get(self, request, *args, **kwargs):
        try:
            self.object = self.get_object()
        except self.model.DoesNotExist:
            self.object = None
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        try:
            self.object = self.get_object()
        except self.model.DoesNotExist:
            self.object = None
        return super().post(request, *args, **kwargs)


class Sortable:

    sortable_fields = []

    def sort_queryset(self, qs):
        sort_key = self.request.GET.get('sort')
        if sort_key:
            plain_key = sort_key[1:] if sort_key.startswith('-') else sort_key
            reverse = not (plain_key == sort_key)
            if plain_key in self.sortable_fields:
                is_text = False
                with suppress(FieldDoesNotExist):
                    is_text = isinstance(qs.model._meta.get_field(plain_key), CharField)

                if is_text:
                    # TODO: this only sorts direct lookups case insensitively
                    # A sorting field like 'speaker__name' will not be found
                    qs = qs.annotate(key=Lower(plain_key)).order_by('-key' if reverse else 'key')
                else:
                    qs = qs.order_by(sort_key)
        return qs


class Filterable:

    filter_fields = []
    default_filters = []

    def filter_queryset(self, qs):
        self._filter_model = qs.model
        for key in self.request.GET:
            lookup_key = key.split('__')[0]
            if lookup_key in self.filter_fields:
                qs = qs.filter(**{key: self.request.GET.get(key)})
        if 'q' in self.request.GET:
            query = urllib.parse.unquote(self.request.GET['q'])
            _filters = [Q(**{field: query}) for field in self.default_filters]
            if len(_filters) > 1:
                _filter = _filters[0]
                for f in _filters[1:]:
                    _filter = _filter | f
                qs = qs.filter(_filter)
            elif len(_filters):
                qs = qs.filter(_filters[0])
        return qs

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['search_form'] = SearchForm(self.request.GET if 'q' in self.request.GET else {})
        # ctx['filter_form'] = use a modelform_factory! that can be done, right?
        return ctx
