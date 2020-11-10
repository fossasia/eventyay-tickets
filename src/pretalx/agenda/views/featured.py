from django.http import HttpResponsePermanentRedirect, HttpResponseRedirect
from django.views.generic import TemplateView
from django_context_decorator import context

from pretalx.common.mixins.views import EventPermissionRequired


def sneakpeek_redirect(request, *args, **kwargs):
    return HttpResponsePermanentRedirect(request.event.urls.featured)


class FeaturedView(EventPermissionRequired, TemplateView):
    template_name = "agenda/featured.html"
    permission_required = "agenda.view_featured_submissions"

    @context
    def talks(self):
        return (
            self.request.event.submissions.filter(is_featured=True)
            .select_related("event", "submission_type")
            .prefetch_related("speakers")
            .order_by("title")
        )

    def dispatch(self, request, *args, **kwargs):
        can_see_featured = self.has_permission()
        can_schedule = request.user.has_perm("agenda.view_schedule", request.event)

        if not can_see_featured and can_schedule:
            return HttpResponseRedirect(request.event.urls.schedule)
        return super().dispatch(request, *args, **kwargs)
