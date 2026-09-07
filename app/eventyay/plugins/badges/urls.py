from django.urls import path

from eventyay.api.urls import event_router
from eventyay.common.urls import OrganizerSlugConverter  # noqa: F401 (registers converter)
from eventyay.plugins.badges.api import (
    BadgeDownloadView,
    BadgeLayoutViewSet,
    BadgePreviewView,
    BadgeProductViewSet,
)

from .views import (
    BadgeCachedDownloadView,
    BadgeSettingsView,
    LayoutCreate,
    LayoutDelete,
    LayoutEditorView,
    LayoutGetDefault,
    LayoutListView,
    LayoutSetDefault,
    LayoutSettingsView,
    OrderPrintDo,
)


urlpatterns = [
    path(
        'control/event/<orgslug:organizer>/<slug:event>/badges/',
        LayoutListView.as_view(),
        name='index',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/badges/settings',
        BadgeSettingsView.as_view(),
        name='event_settings',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/badges/print',
        OrderPrintDo.as_view(),
        name='print',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/badges/getdefault',
        LayoutGetDefault.as_view(),
        name='getdefault',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/badges/add',
        LayoutCreate.as_view(),
        name='add',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/badges/<int:layout>/default',
        LayoutSetDefault.as_view(),
        name='default',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/badges/<int:layout>/delete',
        LayoutDelete.as_view(),
        name='delete',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/badges/<int:layout>/settings',
        LayoutSettingsView.as_view(),
        name='settings',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/badges/<int:layout>/editor',
        LayoutEditorView.as_view(),
        name='edit',
    ),
    path(
        'api/v1/organizers/<orgslug:organizer>/events/<slug:event>/orderpositions/<int:position>/download/badge/',
        BadgeDownloadView.as_view(),
        name='api-badge-download',
    ),
    path(
        'api/v1/organizers/<orgslug:organizer>/events/<slug:event>/orderpositions/<int:position>/preview/badge/',
        BadgePreviewView.as_view(),
        name='badge-preview',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/badges/download/<uuid:id>/',
        BadgeCachedDownloadView.as_view(),
        name='download',
    ),
]

event_router.register('badgelayouts', BadgeLayoutViewSet, basename='badgelayout')
event_router.register('badgeitems', BadgeProductViewSet, basename='badgeproduct')
