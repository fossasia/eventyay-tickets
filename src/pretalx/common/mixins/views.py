import urllib
from contextlib import suppress
from importlib import import_module
from urllib.parse import quote

from django import forms
from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db.models import CharField, Q
from django.db.models.functions import Lower
from django.forms import ValidationError
from django.http import Http404
from django.shortcuts import redirect
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django_context_decorator import context
from formtools.wizard.forms import ManagementForm
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

    @context
    @cached_property
    def action(self):
        if not any(_id in self.kwargs for _id in ['pk', 'code']):
            return 'create'
        if self.request.user.has_perm(
            self.write_permission_required, self.permission_object
        ):
            return 'edit'
        return 'view'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['read_only'] = self.action == 'view'
        if hasattr(self.request, 'event') and issubclass(
            self.form_class, I18nModelForm
        ):
            kwargs['locales'] = self.request.event.locales
        return kwargs


class Sortable:
    """
    In the main class, you'll have to call sort_queryset() in get_queryset.
    In the template, do this:

        {% load url_replace %}
        <th>
            {% trans "Title" %}
            <a href="?{% url_replace request 'sort' '-title' %}"><i class="fa fa-caret-down"></i></a>
            <a href="?{% url_replace request 'sort' 'title' %}"><i class="fa fa-caret-up"></i></a>
        </th>
    """

    sortable_fields = []

    def sort_queryset(self, qs):
        sort_key = self.request.GET.get('sort')
        if not sort_key or sort_key == 'default':
            sort_key = getattr(self, 'default_sort_field', '')
        if sort_key:
            plain_key = sort_key[1:] if sort_key.startswith('-') else sort_key
            reverse = not plain_key == sort_key
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

    @context
    @cached_property
    def search_form(self):
        return SearchForm(self.request.GET if 'q' in self.request.GET else None)

    @context
    @cached_property
    def filter_form(self):
        if hasattr(self, 'filter_form_class'):
            return self.filter_form_class(self.request.event, self.request.GET)
        if hasattr(self, 'get_filter_form'):
            return self.get_filter_form()
        if self.filter_fields:
            _form = forms.modelform_factory(
                self.model, fields=self.filter_fields
            )(self.request.GET)
            for field in _form.fields.values():
                field.required = False
                if hasattr(field, 'queryset'):
                    field.queryset = field.queryset.filter(event=self.request.event)
            return _form
        return None


class PermissionRequired(PermissionRequiredMixin):

    def has_permission(self):
        if not hasattr(self, 'get_permission_object') and hasattr(self, 'object'):
            self.get_permission_object = lambda self: self.object
        result = super().has_permission()
        if not result:
            request = getattr(self, 'request', None)
            if request and hasattr(request, 'event'):
                key = f'pretalx_event_access_{request.event.pk}'
                if key in request.session:
                    sparent = SessionStore(request.session.get(key))
                    parentdata = []
                    with suppress(Exception):
                        parentdata = sparent.load()
                    return 'event_access' in parentdata
        return result

    def get_login_url(self):
        """We do this to avoid leaking data about existing pages."""
        raise Http404()

    def handle_no_permission(self):
        request = getattr(self, 'request', None)
        if (
            request
            and hasattr(request, 'event')
            and request.user.is_anonymous
            and 'cfp' in request.resolver_match.namespaces
        ):
            params = '&' + request.GET.urlencode() if request.GET else ''
            return redirect(
                request.event.urls.login + f'?next={quote(request.path)}' + params
            )
        raise Http404()


class EventPermissionRequired(PermissionRequired):
    def get_permission_object(self):
        return self.request.event


class SensibleBackWizardMixin():

    def post(self, *args, **kwargs):
        """
        Don't redirect if user presses the prev. step button, save data instead.
        The rest of this is copied from WizardView.
        We want to save data when hitting "back"!
        """
        wizard_goto_step = self.request.POST.get('wizard_goto_step', None)
        management_form = ManagementForm(self.request.POST, prefix=self.prefix)
        if not management_form.is_valid():
            raise ValidationError(
                _('ManagementForm data is missing or has been tampered.'),
                code='missing_management_form',
            )

        form_current_step = management_form.cleaned_data['current_step']
        if (form_current_step != self.steps.current and
                self.storage.current_step is not None):
            # form refreshed, change current step
            self.storage.current_step = form_current_step

        # get the form for the current step
        form = self.get_form(data=self.request.POST, files=self.request.FILES)

        # and try to validate
        if form.is_valid():
            # if the form is valid, store the cleaned data and files.
            self.storage.set_step_data(self.steps.current, self.process_step(form))
            self.storage.set_step_files(self.steps.current, self.process_step_files(form))

            # check if the current step is the last step
            if wizard_goto_step and wizard_goto_step in self.get_form_list():
                return self.render_goto_step(wizard_goto_step)
            if self.steps.current == self.steps.last:
                # no more steps, render done view
                return self.render_done(form, **kwargs)
            # proceed to the next step
            return self.render_next_step(form)
        return self.render(form)
