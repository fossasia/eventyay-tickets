from asyncio import Event
from django.contrib import admin
from .models import (
    auth,
    base,
    billing,
    checkin,
    choices,
    devices,
    event,
    fields,
    giftcards,
    invoices,
    items,
    log,
    notifications,
    orders,
    organizer,
    page,
    seating,
    tax,
    vouchers,
    waitinglist,
)

admin.site.register(auth.User)
admin.site.register(event.Event)
admin.site.register(orders.Order)
admin.site.register(organizer.Organizer)
admin.site.register(checkin.Checkin)
