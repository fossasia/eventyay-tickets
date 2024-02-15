import urllib
from collections import defaultdict
from contextlib import suppress
from urllib.parse import quote

from csp.decorators import csp_exempt
from django import forms
from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db.models import CharField, Q
from django.db.models.functions import Lower
from django.forms import ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import redirect
from django.utils.functional import cached_property
from django.utils.module_loading import import_string
from django.utils.translation import gettext_lazy as _
from django_context_decorator import context
from formtools.wizard.forms import ManagementForm
from i18nfield.forms import I18nModelForm
from rules.contrib.views import PermissionRequiredMixin

from pretalx.common.forms import SearchForm

SessionStore = import_string(f"{settings.SESSION_ENGINE}.SessionStore")


class ActionFromUrl:
    write_permission_required = None
    create_permission_required = None

    @cached_property
    def object(self):
        return self.get_object()

    @cached_property
    def permission_object(self):
        if hasattr(self, "get_permission_object"):
            return self.get_permission_object()
        return self.object

    def _check_permission(self, permission_name):
        return self.request.user.has_perm(permission_name, self.permission_object)

    @context
    @cached_property
    def action(self):
        if not any(_id in self.kwargs for _id in ["pk", "code"]):
            if self._check_permission(
                self.create_permission_required or self.write_permission_required
            ):
                return "create"
            return "view"
        if self._check_permission(self.write_permission_required):
            return "edit"
        return "view"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["read_only"] = self.action == "view"
        event = getattr(self.request, "event", None)
        if event and issubclass(self.form_class, I18nModelForm):
            kwargs["locales"] = event.locales
        return kwargs


class Sortable:
    """
    Handles queryset sorting. Will figure out if a field is a text field and sort by
    Lower() if so.

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
    secondary_sort = {}
    default_sort_field = None

    def _get_secondary_sort(self, key):
        secondary_sort_config = getattr(self, "secondary_sort", None) or {}
        return list(secondary_sort_config.get(key, []) or [])

    def _sort_queryset(self, qs, fields):
        fields = [k for k in fields if k]
        # If the model does not have a Meta.ordering, we need to add a
        # final sort key to make sure the sorting is stable.
        if not qs.model._meta.ordering and "pk" not in fields and "-pk" not in fields:
            fields += ["pk"]
        if fields:
            qs = qs.order_by(*fields)
        return qs

    def sort_queryset(self, qs):
        sort_key = self.request.GET.get("sort") or ""
        if not sort_key or sort_key == "default":
            sort_key = getattr(self, "default_sort_field", None) or ""
        plain_key = sort_key[1:] if sort_key.startswith("-") else sort_key
        if plain_key not in self.sortable_fields:
            return self._sort_queryset(qs, self._get_secondary_sort(""))

        is_text = False
        if "__" not in plain_key:
            with suppress(FieldDoesNotExist):
                is_text = isinstance(qs.model._meta.get_field(plain_key), CharField)
        else:
            split_key = plain_key.split("__")
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
            qs = qs.annotate(key=Lower(plain_key))
            sort_key = "-key" if plain_key != sort_key else "key"

        return self._sort_queryset(qs, [sort_key] + self._get_secondary_sort(plain_key))


class Filterable:
    filter_fields = []
    default_filters = []

    def get_default_filters(self):
        return self.default_filters

    def filter_queryset(self, qs):
        if self.filter_fields:
            qs = self._handle_filter(qs)
        if "q" in self.request.GET:
            query = urllib.parse.unquote(self.request.GET["q"])
            qs = self.handle_search(qs, query, self.get_default_filters())
        return qs

    def _handle_filter(self, qs):
        for key in self.request.GET:  # Do NOT use items() to preserve multivalue fields
            # There is a special case here: we hack in OR lookups by allowing __ in values.
            lookups = defaultdict(list)
            values = self.request.GET.getlist(key)
            for value in values:
                value_parts = value.split("__", maxsplit=1)
                if len(value_parts) > 1 and value_parts[0] in self.filter_fields:
                    _key = value_parts[0]
                    _value = value_parts[1]
                else:
                    _key = key
                    _value = value_parts[0]
                if _key in self.filter_fields and _value:
                    if "__isnull" in _key:
                        # We don't append to the list here, because that's not meaningful
                        # in a boolean lookup
                        lookups[_key] = True if _value == "on" else False
                    else:
                        _key = f"{_key}__in"
                        lookups[_key].append(_value)
            _filters = Q()
            for _key, value in lookups.items():
                _filters |= Q(**{_key: value})
            qs = qs.filter(_filters)
        return qs

    @staticmethod
    def handle_search(qs, query, filters):
        _filters = [Q(**{field: query}) for field in filters]
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
        return SearchForm(self.request.GET if "q" in self.request.GET else None)

    @context
    @cached_property
    def filter_form(self):
        if hasattr(self, "filter_form_class"):
            return self.filter_form_class(self.request.event, self.request.GET)
        if hasattr(self, "get_filter_form"):
            return self.get_filter_form()
        if self.filter_fields:
            _form = forms.modelform_factory(self.model, fields=self.filter_fields)(
                self.request.GET
            )
            for field in _form.fields.values():
                field.required = False
                if hasattr(field, "queryset"):
                    field.queryset = field.queryset.filter(event=self.request.event)
            return _form
        return None


class PermissionRequired(PermissionRequiredMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not hasattr(self, "get_permission_object"):
            for key in ("permission_object", "object"):
                if getattr(self, key, None):
                    self.get_permission_object = lambda self: getattr(self, key)  # noqa

    def has_permission(self):
        result = super().has_permission()
        if not result:
            request = getattr(self, "request", None)
            if request and hasattr(request, "event"):
                key = f"pretalx_event_access_{request.event.pk}"
                if key in request.session:
                    sparent = SessionStore(request.session.get(key))
                    parentdata = []
                    with suppress(Exception):
                        parentdata = sparent.load()
                    return "event_access" in parentdata
        return result

    def get_login_url(self):
        """We do this to avoid leaking data about existing pages."""
        raise Http404()

    def handle_no_permission(self):
        request = getattr(self, "request", None)
        if (
            request
            and hasattr(request, "event")
            and request.user.is_anonymous
            and "cfp" in request.resolver_match.namespaces
        ):
            params = "&" + request.GET.urlencode() if request.GET else ""
            return redirect(
                request.event.urls.login + f"?next={quote(request.path)}" + params
            )
        raise Http404()


class EventPermissionRequired(PermissionRequired):
    def get_permission_object(self):
        return self.request.event


class SensibleBackWizardMixin:
    def post(self, *args, **kwargs):
        """Don't redirect if user presses the prev.

        step button, save data instead. The rest of this is copied from
        WizardView. We want to save data when hitting "back"!
        """
        wizard_goto_step = self.request.POST.get("wizard_goto_step", None)
        management_form = ManagementForm(self.request.POST, prefix=self.prefix)
        if not management_form.is_valid():
            raise ValidationError(
                _("ManagementForm data is missing or has been tampered with."),
                code="missing_management_form",
            )

        form_current_step = management_form.cleaned_data["current_step"]
        if (
            form_current_step != self.steps.current
            and self.storage.current_step is not None
        ):
            # form refreshed, change current step
            self.storage.current_step = form_current_step

        # get the form for the current step
        form = self.get_form(data=self.request.POST, files=self.request.FILES)

        # and try to validate
        if form.is_valid():
            # if the form is valid, store the cleaned data and files.
            self.storage.set_step_data(self.steps.current, self.process_step(form))
            self.storage.set_step_files(
                self.steps.current, self.process_step_files(form)
            )

            # check if the current step is the last step
            if wizard_goto_step and wizard_goto_step in self.get_form_list():
                return self.render_goto_step(wizard_goto_step)
            if self.steps.current == self.steps.last:
                # no more steps, render done view
                return self.render_done(form, **kwargs)
            # proceed to the next step
            return self.render_next_step(form)
        return self.render(form)


class SocialMediaCardMixin:
    def get_image(self):
        raise NotImplementedError

    @csp_exempt
    def get(self, request, *args, **kwargs):
        try:
            image = self.get_image()
            if image:
                return FileResponse(image)
        except Exception:
            pass
        if self.request.event.logo:
            return FileResponse(self.request.event.logo)
        if self.request.event.header_image:
            return FileResponse(self.request.event.header_image)
        raise Http404()


class PaginationMixin:
    # TODO: possible make this into a PretalxListView, to make things easier for
    # plugin developers

    DEFAULT_PAGINATION = 50

    def get_paginate_by(self, queryset):
        skey = "stored_page_size_" + self.request.resolver_match.url_name
        default = (
            self.request.session.get(skey)
            or self.paginate_by
            or self.DEFAULT_PAGINATION
        )
        if self.request.GET.get("page_size"):
            try:
                max_page_size = getattr(self, "max_page_size", 250)
                size = min(max_page_size, int(self.request.GET.get("page_size")))
                self.request.session[skey] = size
                return size
            except ValueError:
                return default
        return default

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_size"] = self.get_paginate_by(None)
        ctx["pagination_sizes"] = [50, 100, 250]
        return ctx
