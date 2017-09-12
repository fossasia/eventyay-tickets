from django.db.models import Q
from django.views.generic.detail import SingleObjectTemplateResponseMixin
from django.views.generic.edit import ModelFormMixin, ProcessFormView
from i18nfield.forms import I18nModelForm


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

    def get_queryset(self):
        qs = super().get_queryset()
        return self.sort_queryset(qs)

    def sort_queryset(self, qs):
        qs = super().get_queryset()
        sort_key = self.request.GET.get('sort')
        if sort_key:
            if sort_key in self.sortable_fields or (sort_key.startswith('-') and sort_key[1:] in self.sortable_fields):
                qs = qs.order_by(sort_key)
        return qs


class Filterable:

    filter_fields = []
    default_filters = []

    def get_queryset(self):
        qs = super().get_queryset()
        return self.filter_queryset(qs)

    def filter_queryset(self, qs):
        for key in self.request.GET:
            lookup_key = key.split('__')[0]
            if lookup_key in self.filter_fields:
                qs = qs.filter(**{key: self.request.GET.get(key)})
        if 'q' in self.request.GET:
            query = self.request.GET['q']
            _filters = [Q(**{field: query}) for field in self.default_filters]
            if len(_filters) > 1:
                _filter = _filters[0]
                for f in _filters[1:]:
                    _filter = _filter | f
                qs = qs.filter(_filter)
            elif len(_filters):
                qs = qs.filter(_filters[0])
        return qs
