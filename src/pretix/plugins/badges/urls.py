from django.urls import re_path as url

from pretix.api.urls import event_router
from pretix.plugins.badges.api import (
    BadgeDownloadView,
    BadgeItemViewSet,
    BadgeLayoutViewSet,
    BadgePreviewView,
)

from .views import (
    LayoutCreate,
    LayoutDelete,
    LayoutEditorView,
    LayoutListView,
    LayoutSetDefault,
    LayoutUpdate,
    OrderPrintDo,
)

urlpatterns = [
    url(
        r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/badges/$',
        LayoutListView.as_view(),
        name='index',
    ),
    url(
        r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/badges/print$',
        OrderPrintDo.as_view(),
        name='print',
    ),
    url(
        r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/badges/add$',
        LayoutCreate.as_view(),
        name='add',
    ),
    url(
        r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/badges/(?P<layout>\d+)/default$',
        LayoutSetDefault.as_view(),
        name='default',
    ),
    url(
        r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/badges/(?P<layout>\d+)/delete$',
        LayoutDelete.as_view(),
        name='delete',
    ),
    url(
        r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/badges/(?P<layout>\d+)/edit$',
        LayoutUpdate.as_view(),
        name='update',
    ),
    url(
        r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/badges/(?P<layout>\d+)/editor',
        LayoutEditorView.as_view(),
        name='edit',
    ),
    url(
        r'^api/v1/organizers/(?P<organizer>[^/]+)/events/(?P<event>[^/]+)/orderpositions/(?P<position>\d+)/download/badge/$',
        BadgeDownloadView.as_view(),
        name='api-badge-download',
    ),
    url(
        r'^api/v1/organizers/(?P<organizer>[^/]+)/events/(?P<event>[^/]+)/orderpositions/(?P<position>\d+)/preview/badge/$',
        BadgePreviewView.as_view(),
        name='badge-preview',
    ),
]

event_router.register('badgelayouts', BadgeLayoutViewSet)
event_router.register('badgeitems', BadgeItemViewSet)
