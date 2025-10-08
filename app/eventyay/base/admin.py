from django.contrib import admin
from django.http import HttpRequest
from django_scopes import scopes_disabled

from .models import (
    Announcement, AuditLog, auth, base, BBBCall, BBBServer, BillingInvoice, 
    billing, Channel, ChatEvent, checkin, choices, Device, devices, event, 
    Exhibitor, SystemLog, fields, Gate, GiftCard, GiftCardAcceptance, 
    GiftCardTransaction, giftcards, Invoice, invoices, JanusServer, log, notifications, Order, OrderPayment, OrderRefund, 
    orders, organizer, page, Poll, Poster, roomquestion, Quota, Room, roulette, 
    seating, StreamingServer, tax, Team, TeamInvite, TurnServer, vouchers, 
    WaitingListEntry, waitinglist, room, exhibitor, poll, poster, chat
)
from ..api.models import OAuthApplication, OAuthAccessToken, OAuthRefreshToken, OAuthIDToken, WebHook, WebHookCall, ApiCall, WebHookEventListener

# User and Authentication

class TeamAdmin(admin.ModelAdmin):
    filter_horizontal = ('members', 'limit_events')

    # The Team model has ManyToMany relation to Track model, which is scoped to Event.
    # We need to disable the scopes because the admin view does not have an event in context.
    @scopes_disabled()
    def change_view(self, request: HttpRequest, object_id, form_url = '', extra_context = None):
        return super().change_view(request, object_id, form_url, extra_context)


admin.site.register(auth.User)
admin.site.register(auth.U2FDevice)
admin.site.register(auth.WebAuthnDevice)

# Event Management
admin.site.register(event.Event)
admin.site.register(event.SubEvent)
admin.site.register(event.EventLock)
admin.site.register(event.EventMetaProperty)
admin.site.register(event.EventMetaValue)
admin.site.register(event.SubEventMetaValue)
admin.site.register(event.RequiredAction)

# Organizer Management
admin.site.register(organizer.Team, TeamAdmin)
admin.site.register(TeamInvite)

# Orders and Payments
admin.site.register(Order)
admin.site.register(OrderPayment)
admin.site.register(OrderRefund)
admin.site.register(orders.OrderPosition)
admin.site.register(orders.CartPosition)
admin.site.register(orders.OrderFee)
admin.site.register(orders.InvoiceAddress)
admin.site.register(orders.QuestionAnswer)
admin.site.register(orders.CachedTicket)
admin.site.register(orders.CachedCombinedTicket)
admin.site.register(orders.CancellationRequest)
admin.site.register(orders.RevokedTicketSecret)
admin.site.register(checkin.Checkin)
admin.site.register(checkin.CheckinList)

# Devices and Gates
admin.site.register(Device)
admin.site.register(Gate)

# Invoicing
admin.site.register(Invoice)
admin.site.register(invoices.InvoiceLine)
admin.site.register(BillingInvoice)

# Gift Cards
admin.site.register(GiftCard)
admin.site.register(GiftCardAcceptance)
admin.site.register(GiftCardTransaction)

# Vouchers and Waiting List
admin.site.register(vouchers.Voucher)
admin.site.register(vouchers.InvoiceVoucher)
admin.site.register(WaitingListEntry)

# Seating and Rooms
admin.site.register(seating.SeatingPlan)
admin.site.register(seating.Seat)
admin.site.register(seating.SeatCategoryMapping)
admin.site.register(Room)
admin.site.register(room.RoomView)
admin.site.register(room.Reaction)

# Exhibitors
admin.site.register(Exhibitor)
admin.site.register(exhibitor.ExhibitorLink)
admin.site.register(exhibitor.ExhibitorSocialMediaLink)
admin.site.register(exhibitor.ExhibitorStaff)
admin.site.register(exhibitor.ExhibitorView)
admin.site.register(exhibitor.ContactRequest)

# Polls and Questions
admin.site.register(Poll)
admin.site.register(poll.PollOption)
admin.site.register(poll.PollVote)
admin.site.register(roomquestion.RoomQuestion)
admin.site.register(roomquestion.QuestionVote)

# Posters
admin.site.register(Poster)
admin.site.register(poster.PosterPresenter)
admin.site.register(poster.PosterVote)
admin.site.register(poster.PosterLink)

# Chat and Communication
admin.site.register(Channel)
admin.site.register(ChatEvent)
admin.site.register(chat.ChatEventReaction)
admin.site.register(chat.ChatEventNotification)
admin.site.register(chat.Membership)

# Roulette
admin.site.register(roulette.RouletteRequest)
admin.site.register(roulette.RoulettePairing)

# Servers and Infrastructure
admin.site.register(BBBServer)
admin.site.register(BBBCall)
admin.site.register(JanusServer)
admin.site.register(TurnServer)
admin.site.register(StreamingServer)

# Tax and Billing
admin.site.register(tax.TaxRule)

# Pages and Content
admin.site.register(page.Page)
admin.site.register(Announcement)
admin.site.register(SystemLog)

# Logging and Audit
admin.site.register(log.LogEntry)
admin.site.register(AuditLog)
admin.site.register(base.CachedFile)

# Notifications
admin.site.register(notifications.NotificationSetting)

# API and OAuth
admin.site.register(WebHook)
admin.site.register(WebHookEventListener)
admin.site.register(WebHookCall)
admin.site.register(ApiCall)
