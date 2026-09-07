import importlib

from django.apps import apps
from django.http import HttpResponsePermanentRedirect
from django.urls import include, path
from rest_framework import routers

from eventyay.api.views import cart
from eventyay.common.urls import OrganizerSlugConverter  # noqa: F401 (registers converter)

from .views import (
    access_code,
    checkin,
    device,
    event,
    exporters,
    feedback,
    loungemesh,
    mail,
    oauth,
    order,
    organizer,
    product,
    question,
    review,
    room,
    schedule,
    speaker,
    speaker_information,
    stream_schedule,
    submission,
    upload,
    user,
    version,
    voucher,
    waitinglist,
    webhooks,
)
from .views.stripe import stripe_webhook_view


def talks_to_submissions_redirect(request, event, subpath):
    """
    Redirects requests from /events/.../talks/... to /events/.../submissions/...
    preserving the subpath and query parameters.
    """
    new_path = request.path.replace('/talks/', '/submissions/', 1)

    if query_string := request.META.get('QUERY_STRING', ''):
        new_path += f'?{query_string}'

    return HttpResponsePermanentRedirect(new_path)


router = routers.DefaultRouter()
router.register(r'organizers', organizer.OrganizerViewSet)

orga_router = routers.DefaultRouter()
orga_router.register(r'events', event.EventViewSet, basename='events')
orga_router.register(r'subevents', event.SubEventViewSet, basename='subevents')
orga_router.register(r'webhooks', webhooks.WebHookViewSet)
orga_router.register(r'seatingplans', organizer.SeatingPlanViewSet)
orga_router.register(r'giftcards', organizer.GiftCardViewSet)
orga_router.register(r'teams', organizer.TeamViewSet)
orga_router.register(r'devices', organizer.DeviceViewSet)
orga_router.register(r'exporters', exporters.OrganizerExportersViewSet, basename='exporters')

team_router = routers.DefaultRouter()
team_router.register(r'members', organizer.TeamMemberViewSet)
team_router.register(r'invites', organizer.TeamInviteViewSet)
team_router.register(r'tokens', organizer.TeamAPITokenViewSet)

event_router = routers.DefaultRouter()
event_router.register(r'subevents', event.SubEventViewSet, basename='subevents')
event_router.register(r'clone', event.CloneEventViewSet, basename='clone')
event_router.register(r'products', product.ProductViewSet)
event_router.register(r'categories', product.ProductCategoryViewSet)
event_router.register(r'questions', product.QuestionViewSet)
event_router.register(r'quotas', product.QuotaViewSet)
event_router.register(r'vouchers', voucher.VoucherViewSet)
event_router.register(r'orders', order.OrderViewSet)
event_router.register(r'orderpositions', order.OrderPositionViewSet)
event_router.register(r'invoices', order.InvoiceViewSet)
event_router.register(r'revokedsecrets', order.RevokedSecretViewSet, basename='revokedsecrets')
event_router.register(r'taxrules', event.TaxRuleViewSet, basename='taxrules')
event_router.register(r'waitinglistentries', waitinglist.WaitingListViewSet)
event_router.register(r'checkinlists', checkin.CheckinListViewSet)
event_router.register(r'cartpositions', cart.CartPositionViewSet)
event_router.register(r'exporters', exporters.EventExportersViewSet, basename='exporters')
event_router.register('submissions', submission.SubmissionViewSet, basename='submission')
event_router.register('schedules', schedule.ScheduleViewSet, basename='schedule')
event_router.register('slots', schedule.TalkSlotViewSet, basename='slots')
event_router.register('tags', submission.TagViewSet, basename='tag')
event_router.register('submission-types', submission.SubmissionTypeViewSet, basename='submission_type')
event_router.register('tracks', submission.TrackViewSet, basename='track')
event_router.register('mail-templates', mail.MailTemplateViewSet, basename='mail_template')
event_router.register('access-codes', access_code.SubmitterAccessCodeViewSet, basename='access_code')
event_router.register('speakers', speaker.SpeakerViewSet, basename='speaker')
event_router.register('reviews', review.ReviewViewSet, basename='review')
event_router.register('rooms', room.RoomViewSet, basename='room')
event_router.register('talkquestions', question.QuestionViewSet, basename='talkquestion')
event_router.register('answers', question.AnswerViewSet, basename='answer')
event_router.register('question-options', question.AnswerOptionViewSet, basename='question_option')
event_router.register('speaker-information', speaker_information.SpeakerInformationViewSet, basename='speaker_information')
event_router.register('feedback', feedback.FeedbackViewSet, basename='feedback')

checkinlist_router = routers.DefaultRouter()
checkinlist_router.register(r'positions', checkin.CheckinListPositionViewSet, basename='checkinlistpos')

question_router = routers.DefaultRouter()
question_router.register(r'options', product.QuestionOptionViewSet)

room_router = routers.DefaultRouter()
room_router.register(r'stream-schedules', stream_schedule.StreamScheduleViewSet, basename='stream-schedule')

product_router = routers.DefaultRouter()
product_router.register(r'variations', product.ProductVariationViewSet)
product_router.register(r'addons', product.ProductAddOnViewSet)
product_router.register(r'bundles', product.ProductBundleViewSet)

order_router = routers.DefaultRouter()
order_router.register(r'payments', order.PaymentViewSet)
order_router.register(r'refunds', order.RefundViewSet)

giftcard_router = routers.DefaultRouter()
giftcard_router.register(r'transactions', organizer.GiftCardTransactionViewSet)

# Force import of all plugins to give them a chance to register URLs with the router
for app in apps.get_app_configs():
    if hasattr(app, 'EventyayPluginMeta'):
        if importlib.util.find_spec(app.name + '.urls'):
            importlib.import_module(app.name + '.urls')

importlib.import_module('eventyay.plugins.ticketoutputpdf.urls')

urlpatterns = [
    path('', include(router.urls)),
    path('organizers/<orgslug:organizer>/', include(orga_router.urls)),
    path(
        'organizers/<orgslug:organizer>/settings/',
        organizer.OrganizerSettingsView.as_view(),
        name='organizer.settings',
    ),
    path(
        'organizers/<orgslug:organizer>/giftcards/<giftcard>/',
        include(giftcard_router.urls),
    ),
    path(
        'organizers/<orgslug:organizer>/events/<slug:event>/settings/',
        event.EventSettingsView.as_view(),
        name='event.settings',
    ),
    path(
        'organizers/<orgslug:organizer>/events/<slug:event>/publish-talks/',
        event.EventPublishTalksView.as_view(),
        name='event.publish-talks',
    ),
    path(
        'organizers/<orgslug:organizer>/events/<slug:event>/publish-tickets/',
        event.EventPublishTicketsView.as_view(),
        name='event.publish-tickets',
    ),
    path(
        'organizers/<orgslug:organizer>/events/<slug:event>/enable-manual-payment/',
        event.EventEnableManualPaymentView.as_view(),
        name='event.enable-manual-payment',
    ),
    path(
        'organizers/<orgslug:organizer>/events/<slug:event>/speakers/import/',
        speaker.SpeakerImportView.as_view(),
        name='speaker.import',
    ),
    path(
        'organizers/<orgslug:organizer>/events/<slug:event>/submissions/import/',
        submission.SubmissionImportView.as_view(),
        name='submission.import',
    ),
    path(
        'organizers/<orgslug:organizer>/events/<slug:event>/',
        include(event_router.urls),
    ),
    path(
        'organizers/<orgslug:organizer>/teams/<slug:team>/',
        include(team_router.urls),
    ),
    path(
        'organizers/<orgslug:organizer>/events/<slug:event>/products/<slug:product>/',
        include(product_router.urls),
    ),
    path(
        'organizers/<orgslug:organizer>/events/<slug:event>/questions/<slug:question>/',
        include(question_router.urls),
    ),
    path(
        'organizers/<orgslug:organizer>/events/<slug:event>/checkinlists/<slug:list>/',
        include(checkinlist_router.urls),
    ),
    path(
        'organizers/<orgslug:organizer>/checkin/redeem/',
        checkin.CheckinRedeemView.as_view(),
        name='checkin.redeem',
    ),
    path(
        'organizers/<orgslug:organizer>/events/<slug:event>/orders/<int:order>/',
        include(order_router.urls),
    ),
    path(
        'organizers/<orgslug:organizer>/events/<slug:event>/rooms/<int:room_pk>/',
        include(room_router.urls),
    ),
    path('oauth/authorize', oauth.AuthorizationView.as_view(), name='authorize'),
    path('oauth/token', oauth.TokenView.as_view(), name='token'),
    path('oauth/revoke_token', oauth.RevokeTokenView.as_view(), name='revoke-token'),
    path(
        'device/initialize',
        device.InitializeView.as_view(),
        name='device.initialize',
    ),
    path('device/update', device.UpdateView.as_view(), name='device.update'),
    path('device/session', device.SessionView.as_view(), name='device.session'),
    path(
        'device/verify-setup-token',
        device.VerifySetupTokenView.as_view(),
        name='device.verify-setup-token',
    ),
    path('device/roll', device.RollKeyView.as_view(), name='device.roll'),
    path('device/revoke', device.RevokeKeyView.as_view(), name='device.revoke'),
    path(
        'device/eventselection',
        device.EventSelectionView.as_view(),
        name='device.eventselection',
    ),
    path('upload', upload.UploadView.as_view(), name='upload'),
    path('me', user.MeView.as_view(), name='user.me'),
    path('version', version.VersionView.as_view(), name='version'),
    path('webhook/stripe', stripe_webhook_view, name='stripe-webhook'),
    path('webhook/stripe/', stripe_webhook_view, name='stripe-webhook-slash'),
    path(
        '<orgslug:organizer>/<slug:event>/schedule-public',
        event.talk_schedule_public,
        name='event.schedule-public',
    ),
    path(
        '<orgslug:organizer>/<slug:event>/ticket-check',
        event.CustomerOrderCheckView.as_view(),
        name='event.ticket-check',
    ),
    # We redirect the old pre-filtered /talks/ endpoint to  /submissions/
    path(
        'events/<slug:event>/talks/<path:subpath>',
        talks_to_submissions_redirect,
        name='event_talks_redirect',
    ),
    # The favourites endpoints are separate, as they are functions, not viewsets.
    # They need to be separate from the viewset in order to permit session
    # authentication.
    path(
        'events/<slug:event>/submissions/favourites/',
        submission.favourites_view,
        name='submission.favourites',
    ),
    path(
        'events/<slug:event>/submissions/<slug:code>/favourite/',
        submission.favourite_view,
        name='submission.favourite',
    ),
    path(
        'events/<slug:event>/submissions/favourites/merge/',
        submission.favourites_merge_view,
        name='submission.favourites.merge',
    ),
    path(
        'events/<slug:event>/rooms/<int:room_pk>/',
        include(room_router.urls),
    ),
    path(
        'events/<slug:event>/favourite-talk/',
        submission.SubmissionFavouriteDeprecatedView.as_view(),
    ),
    path(
        'loungemesh/token/',
        loungemesh.LoungeMeshTokenExchangeView.as_view(),
        name='loungemesh.token',
    ),
    path(
        'loungemesh/token/refresh/',
        loungemesh.LoungeMeshTokenRefreshView.as_view(),
        name='loungemesh.token.refresh',
    ),
    path('events/<slug:event>/', include(event_router.urls)),
]
