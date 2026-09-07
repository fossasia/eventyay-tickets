from logging import getLogger

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.utils.functional import cached_property
from django.views.generic.list import ListView

from eventyay.base.models import Submission
from eventyay.control.views import PaginationMixin

from ..forms.filters import SessionsFilterForm


logger = getLogger(__name__)


class MySessionsView(LoginRequiredMixin, PaginationMixin, ListView):
    template_name = 'eventyay_common/sessions/sessions.html'
    paginate_by = 25

    @cached_property
    def filter_form(self):
        return SessionsFilterForm(self.request.GET, user=self.request.user)

    def get_queryset(self):
        from django_scopes import scopes_disabled
        user = self.request.user
        with scopes_disabled():
            qs = (
                Submission.objects
                .filter(speakers__email__iexact=user.email)
                .select_related('event', 'event__organizer', 'submission_type')
                .order_by('-event__date_from')
            )

        if self.filter_form.is_valid():
            event = self.filter_form.cleaned_data.get('event')
            search = self.filter_form.cleaned_data.get('search')

            if event:
                qs = qs.filter(event=event)

            if search:
                qs = qs.filter(title__icontains=search)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filter_form
        ctx['has_active_filters'] = self.filter_form.has_active_filters()
        return ctx

    def get(self, request, *args, **kwargs):
        # If filter form is invalid, strip the 'event' from URL and redirect to this new URL.
        if not self.filter_form.is_valid():
            new_url_query = request.GET.copy()
            new_url_query.pop('event', None)
            new_url = request.path + '?' + new_url_query.urlencode()
            logger.info('To redirect to "%s" because the filter values are invalid.', new_url)
            return redirect(new_url)
        return super().get(request, *args, **kwargs)
