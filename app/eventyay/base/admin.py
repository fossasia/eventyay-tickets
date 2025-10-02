from django.contrib import admin
from django.http import HttpRequest
from django_scopes import scopes_disabled

from .models import (
    auth,
    checkin,
    event,
    orders,
    organizer,
)


class TeamAdmin(admin.ModelAdmin):
    filter_horizontal = ('members', 'limit_events')

    # The Team model has ManyToMany relation to Track model, which is scoped to Event.
    # We need to disable the scopes because the admin view does not have an event in context.
    @scopes_disabled()
    def change_view(self, request: HttpRequest, object_id, form_url = '', extra_context = None):
        return super().change_view(request, object_id, form_url, extra_context)


admin.site.register(auth.User)
admin.site.register(event.Event)
admin.site.register(orders.Order)
admin.site.register(organizer.Organizer)
admin.site.register(organizer.Team, TeamAdmin)
admin.site.register(checkin.Checkin)
