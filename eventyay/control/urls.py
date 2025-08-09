from django.http import HttpResponse
from django.urls import include, path
from django.urls import re_path as url
from django.views.generic.base import RedirectView
from eventyay.control.views import admin

urlpatterns = [
    path('', lambda request: HttpResponse("<div>This is a control index page</div>"), name='index'),
    url(
        r'^admin/',
        include(
            [
                url(r'^$', admin.AdminDashboard.as_view(), name='admin.dashboard'),
                url(r'^organizers/$', admin.OrganizerList.as_view(), name='admin.organizers'),
                url(r'^events/$', admin.AdminEventList.as_view(), name='admin.events'),
                url(r'^task_management/$', admin.TaskList.as_view(), name='admin.task_management'),
                
                # Voucher Management URLs
                url(r'^vouchers/$', admin.VoucherList.as_view(), name='admin.vouchers'),
                url(r'^vouchers/new/$', admin.VoucherCreate.as_view(), name='admin.vouchers.create'),
                url(r'^vouchers/(?P<voucher>\\d+)/$', admin.VoucherUpdate.as_view(), name='admin.vouchers.update'),
                url(r'^vouchers/(?P<voucher>\\d+)/delete/$', admin.VoucherDelete.as_view(), name='admin.vouchers.delete'),
            ]
        ),
    ),
    
    path('video/', include('eventyay.control.video.urls')),
]