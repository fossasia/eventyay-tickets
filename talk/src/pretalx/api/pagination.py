from django.utils.functional import cached_property
from rest_framework import pagination


class LimitOffsetPagination(pagination.LimitOffsetPagination):
    max_limit = 50


class PageNumberPagination(pagination.PageNumberPagination):
    """Provides page number pagination, but while we still support
    the legacy API, can fall back to LimitOffsetPagination if both
    limit and offset are present in the request.
    TODO remove implementation details once the legacy API is getting removed.
    """

    page_size_query_param = "page_size"
    max_page_size = 50

    @cached_property
    def is_limit_offset(self):
        return self.request.GET.get("limit") and self.request.GET.get("offset")

    @cached_property
    def limit_offset_paginator(self):
        return LimitOffsetPagination()

    def paginate_queryset(self, queryset, request, view=None):
        self.request = request
        if self.is_limit_offset:
            return self.limit_offset_paginator.paginate_queryset(
                queryset, request, view=view
            )
        return super().paginate_queryset(queryset, request, view=view)

    def get_paginated_response(self, data):
        if self.is_limit_offset:
            return self.limit_offset_paginator.get_paginated_response(data)
        return super().get_paginated_response(data)
