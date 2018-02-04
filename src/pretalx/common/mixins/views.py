import urllib
from contextlib import suppress

from django.core.exceptions import FieldDoesNotExist
from django.db.models import CharField, Q
from django.db.models.functions import Lower
from django.http import Http404
from django.utils.functional import cached_property
from i18nfield.forms import I18nModelForm
from rules.contrib.views import PermissionRequiredMixin

from pretalx.common.forms import SearchForm


class ActionFromUrl:
    write_permission_required = None

    def get_object(self):
        return None

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
        if self.request.user.has_perm(self.write_permission_required, self.permission_object):
            return 'edit'
        return 'view'

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


class PermissionRequired(PermissionRequiredMixin):

    def get_login_url(self):
        """ We do this to avoid leaking data about existing pages. """
        raise Http404()
