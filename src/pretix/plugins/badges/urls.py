from django.urls import path, re_path

from pretix.api.urls import event_router
from pretix.plugins.badges.api import BadgeItemViewSet, BadgeLayoutViewSet

from .views import (
    LayoutCreate, LayoutDelete, LayoutEditorView, LayoutListView,
    LayoutSetDefault, OrderPrintDo,
)

urlpatterns = [
    path('control/event/<str:organizer>/<str:event>/badges/',
        LayoutListView.as_view(), name='index'),
    path('control/event/<str:organizer>/<str:event>/badges/print',
        OrderPrintDo.as_view(), name='print'),
    path('control/event/<str:organizer>/<str:event>/badges/add',
        LayoutCreate.as_view(), name='add'),
    path('control/event/<str:organizer>/<str:event>/badges/<int:layout>/default',
        LayoutSetDefault.as_view(), name='default'),
    path('control/event/<str:organizer>/<str:event>/badges/<int:layout>/delete',
        LayoutDelete.as_view(), name='delete'),
    re_path(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/badges/(?P<layout>\d+)/editor',
        LayoutEditorView.as_view(), name='edit'),
]
event_router.register('badgelayouts', BadgeLayoutViewSet)
event_router.register('badgeitems', BadgeItemViewSet)
