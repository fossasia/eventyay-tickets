from django.contrib import admin

from .models import (
    auth,
    checkin,
    event,
    orders,
    organizer,
)


class TeamAdmin(admin.ModelAdmin):
    filter_horizontal = ('members', 'limit_events')


admin.site.register(auth.User)
admin.site.register(event.Event)
admin.site.register(orders.Order)
admin.site.register(organizer.Organizer)
admin.site.register(organizer.Team, TeamAdmin)
admin.site.register(checkin.Checkin)
