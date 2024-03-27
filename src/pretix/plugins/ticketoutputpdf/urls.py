from django.urls import path, re_path

from pretix.api.urls import event_router
from pretix.plugins.ticketoutputpdf.api import (
    TicketLayoutItemViewSet, TicketLayoutViewSet,
)
from pretix.plugins.ticketoutputpdf.views import (
    LayoutCreate, LayoutDelete, LayoutEditorView, LayoutGetDefault,
    LayoutListView, LayoutSetDefault,
)

urlpatterns = [
    path('control/event/<str:organizer>/<str:event>/pdfoutput/',
        LayoutListView.as_view(), name='index'),
    path('control/event/<str:organizer>/<str:event>/pdfoutput/add',
        LayoutCreate.as_view(), name='add'),
    path('control/event/<str:organizer>/<str:event>/pdfoutput/<int:layout>/default',
        LayoutSetDefault.as_view(), name='default'),
    path('control/event/<str:organizer>/<str:event>/pdfoutput/default',
        LayoutGetDefault.as_view(), name='getdefault'),
    path('control/event/<str:organizer>/<str:event>/pdfoutput/<int:layout>/delete',
        LayoutDelete.as_view(), name='delete'),
    re_path(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/pdfoutput/(?P<layout>\d+)/editor',
        LayoutEditorView.as_view(), name='edit'),
]
event_router.register('ticketlayouts', TicketLayoutViewSet)
event_router.register('ticketlayoutitems', TicketLayoutItemViewSet)
