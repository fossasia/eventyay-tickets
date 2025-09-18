from django.contrib import admin

from .models import (
    auth,
    checkin,
    event,
    orders,
    organizer,
)


admin.site.register(auth.User)
admin.site.register(event.Event)
admin.site.register(orders.Order)
admin.site.register(organizer.Organizer)
admin.site.register(checkin.Checkin)
