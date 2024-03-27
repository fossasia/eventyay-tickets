from django.urls import path, re_path

from pretix.api.urls import orga_router
from pretix.plugins.banktransfer.api import BankImportJobViewSet

from . import views

urlpatterns = [
    re_path(r'^control/organizer/(?P<organizer>[^/]+)/banktransfer/import/',
        views.OrganizerImportView.as_view(),
        name='import'),
    re_path(r'^control/organizer/(?P<organizer>[^/]+)/banktransfer/job/(?P<job>\d+)/',
        views.OrganizerJobDetailView.as_view(), name='import.job'),
    re_path(r'^control/organizer/(?P<organizer>[^/]+)/banktransfer/action/',
        views.OrganizerActionView.as_view(), name='import.action'),
    re_path(r'^control/organizer/(?P<organizer>[^/]+)/banktransfer/refunds/',
        views.OrganizerRefundExportListView.as_view(), name='refunds.list'),
    path('control/organizer/<str:organizer>/banktransfer/export/<int:id>/',
        views.OrganizerDownloadRefundExportView.as_view(),
        name='refunds.download'),
    path('control/organizer/<str:organizer>/banktransfer/sepa-export/<int:id>/',
        views.OrganizerSepaXMLExportView.as_view(),
        name='refunds.sepa'),

    re_path(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/banktransfer/import/',
        views.EventImportView.as_view(),
        name='import'),
    re_path(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/banktransfer/job/(?P<job>\d+)/',
        views.EventJobDetailView.as_view(), name='import.job'),
    re_path(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/banktransfer/action/',
        views.EventActionView.as_view(), name='import.action'),
    re_path(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/banktransfer/refunds/',
        views.EventRefundExportListView.as_view(),
        name='refunds.list'),
    path('control/event/<str:organizer>/<str:event>/banktransfer/export/<int:id>/',
        views.EventDownloadRefundExportView.as_view(),
        name='refunds.download'),
    path('control/event/<str:organizer>/<str:event>/banktransfer/sepa-export/<int:id>/',
        views.EventSepaXMLExportView.as_view(),
        name='refunds.sepa'),
]

orga_router.register('bankimportjobs', BankImportJobViewSet)
