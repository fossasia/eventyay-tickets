from logging import getLogger

from django.db.models import Q
from django.shortcuts import redirect
from django.utils.functional import cached_property
from django.views.generic.list import ListView

from eventyay.base.models import Order
from eventyay.control.views import PaginationMixin

from ..forms.filters import UserOrderFilterForm

logger = getLogger(__name__)


class MyOrdersView(PaginationMixin, ListView):
    template_name = 'eventyay_common/orders/orders.html'
    paginate_by = 25

    @cached_property
    def filter_form(self):
        return UserOrderFilterForm(self.request.GET, user=self.request.user, request=self.request)

    def get_queryset(self):
        user = self.request.user
        qs = Order.objects.filter(Q(email__iexact=user.email)).select_related('event').order_by('-datetime')

        if self.filter_form.is_valid():
            cleaned = self.filter_form.cleaned_data
            if cleaned.get('event'):
                qs = qs.filter(event=cleaned['event'])
            if code := (cleaned.get('code') or '').strip():
                qs = qs.filter(code__icontains=code)
            if status := cleaned.get('status'):
                qs = qs.filter(status=status)
            if date_from := cleaned.get('date_from'):
                qs = qs.filter(datetime__date__gte=date_from)
            if date_to := cleaned.get('date_to'):
                qs = qs.filter(datetime__date__lte=date_to)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filter_form
        ctx['has_active_filters'] = self.filter_form.has_active_filters()
        return ctx

    def get(self, request, *args, **kwargs):
        # If filter form is invalid, strip the invalid inputs and redirect to a clean URL.
        if not self.filter_form.is_valid():
            new_url_query = request.GET.copy()
            for field_name in self.filter_form.errors:
                new_url_query.pop(field_name, None)
            new_url = request.path + '?' + new_url_query.urlencode()
            logger.info('To redirect to "%s" because the filter values are invalid.', new_url)
            return redirect(new_url)
        return super().get(request, *args, **kwargs)
