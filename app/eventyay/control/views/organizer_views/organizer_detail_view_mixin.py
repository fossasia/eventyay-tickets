from eventyay.base.models.organizer import Organizer
from eventyay.control.signals import nav_organizer


class OrganizerDetailViewMixin:
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['nav_organizer'] = []
        ctx['organizer'] = self.request.organizer

        for recv, retv in nav_organizer.send(
            sender=self.request.organizer,
            request=self.request,
            organizer=self.request.organizer,
        ):
            ctx['nav_organizer'] += retv
        ctx['nav_organizer'].sort(key=lambda n: n['label'])
        return ctx

    def get_object(self, queryset=None) -> Organizer:
        return self.request.organizer
