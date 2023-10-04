"""
This module is loosely inspired by django-tables2, which is a great package,
but turned out to come with a noticeable performance penalty for pretalx.

Differences include:
    - sorting, filtering and pagination is handled outside the table
      and indicators are passed to the table for rendering
    - no automatic table generation
    - no footers
"""
from django.views.generic import ListView
from django.template.loader import get_template
from django.utils.translation import gettext_lazy as _
from django.utils.functional import cached_property
from django_context_decorator import context


class HtmlAttrs(dict):
    def __str__(self):
        return " ".join(f'{k}="{v}"' for k, v in self.items()).strip()


class Column:
    def __init__(self, name, header=None, orderable=False, order_direction=None):
        self.name = name
        self.header = header or name
        self.orderable = orderable
        self.order_direction = order_direction
        self.attrs = {
            "th": HtmlAttrs(),
            "td": HtmlAttrs(),
        }

    @property
    def next_order_string(self):
        if not self.orderable:
            return ""
        if self.order_direction == "asc":
            return f"-{self.name}"
        return f"{self.name}"


class Table:
    template_name = "common/table.html"
    empty_text = _("No data available.")

    def __init__(
        self,
        queryset,
        paginator=None,
        page=None,
        is_paginated=False,
        is_ordered_by=None,
        is_filtered=False,
        show_header=True,
    ):
        self.queryset = queryset
        self.paginator = paginator
        self.page = page
        self.is_paginated = is_paginated
        self.is_ordered_by = is_ordered_by
        self.is_filtered = is_filtered
        self.show_header = show_header
        self.exclude_from_export = []
        self.exclude_from_display = []

        self.columns = self.get_columns()
        self.attrs = {
            "table": HtmlAttrs(class_="table"),
            "thead": HtmlAttrs(),
            "tbody": HtmlAttrs(),
        }

    def get_columns(self):
        pass


    def get_columns(self, purpose="display"):
        # TODO respect column order
        if purpose == "display":
            return [
                column
                for column in columns
                if column.name not in self.exclude_from_display
            ]
        elif purpose == "export":
            return [
                column
                for column in columns
                if column.name not in self.exclude_from_export
            ]
        raise ValueError(f"Unknown purpose: {purpose}")

    def get_data(self, purpose="display"):
        """ purpose can be 'display' or 'export' """
        columns = self.get_columns(purpose=purpose)
        for obj in self.queryset:
            yield [
                # TODO handle non-trivial columns: maybe just column(data).render()?
                # column.render(obj)?
                (column, getattr(obj, column.name))
                for column in columns
            ]

    def as_html(self):
        template = get_template(self.template_name)
        columns = self.get_columns(purpose="display")
        data = self.get_data(purpose="display")
        return template.render({
            "show_header": self.show_header,
            "attrs": self.attrs,
            "columns": columns,
            "rows": data,
        })



class TableView(ListView):
    def get_table_kwargs(self):
        queryset = self.get_queryset()
        page_size = self.get_paginate_by(queryset)

        if not page_size:
            return {"queryset": queryset}

        paginator, page, queryset, is_paginated = self.paginate_queryset(
            queryset, page_size
        )
        # TODO: is_filtered, is_ordered_by
        return {
            "queryset": queryset,
            "page": page,
            "is_paginated": is_paginated,
            "paginator": paginator,
        }

    def get_table(self, **kwargs):
        return self.table_class(**self.get_table_kwargs())

    @context
    @cached_property
    def table(self):
        return self.get_table()
