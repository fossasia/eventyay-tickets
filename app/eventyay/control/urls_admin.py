from django.urls import include
from django.urls import re_path as url
from django.urls import path
from django.views.generic.base import RedirectView

from eventyay.control.views import (
    admin,
    global_settings,
    pages,
    typeahead,
    user,
    users,
    vouchers,
)

app_name = 'eventyay_admin'

urlpatterns = [
    url(r'^$', admin.AdminDashboard.as_view(), name='admin.dashboard'),
    url(r'^organizers/$', admin.OrganizerList.as_view(), name='admin.organizers'),
    url(r'^events/$', admin.AdminEventList.as_view(), name='admin.events'),
    path('attendees/', admin.AttendeeListView.as_view(), name='admin.attendees'),
    path('submissions/', admin.SubmissionListView.as_view(), name='admin.submissions'),
    url(r'^task_management', admin.TaskList.as_view(), name='admin.task_management'),
    url(r'^sudo/(?P<id>\d+)/$', user.EditStaffSession.as_view(), name='admin.user.sudo.edit'),
    url(r'^sudo/sessions/$', user.StaffSessionList.as_view(), name='admin.user.sudo.list'),
    url(r'^users/$', users.UserListView.as_view(), name='admin.users'),
    url(r'^users/select2$', typeahead.users_select2, name='admin.users.select2'),
    url(r'^users/add$', users.UserCreateView.as_view(), name='admin.users.add'),
    url(
        r'^users/impersonate/stop',
        users.UserImpersonateStopView.as_view(),
        name='admin.users.impersonate.stop',
    ),
    url(r'^users/(?P<id>\d+)/$', users.UserEditView.as_view(), name='admin.users.edit'),
    url(r'^users/(?P<id>\d+)/reset$', users.UserResetView.as_view(), name='admin.users.reset'),
    url(
        r'^users/(?P<id>\d+)/impersonate',
        users.UserImpersonateView.as_view(),
        name='admin.users.impersonate',
    ),
    url(r'^users/(?P<id>\d+)/anonymize', users.UserAnonymizeView.as_view(), name='admin.users.anonymize'),
    url(r'^global/settings/$', global_settings.GlobalSettingsView.as_view(), name='admin.global.settings'),
    url(r'^global/update/$', global_settings.UpdateCheckView.as_view(), name='admin.global.update'),
    url(r'^global/message/$', global_settings.MessageView.as_view(), name='admin.global.message'),
    url(
        r'^global/billing_validation/$',
        global_settings.ToggleBillingValidationView.as_view(),
        name='admin.toggle.billing.validation',
    ),
    url(r'^vouchers/$', admin.VoucherList.as_view(), name='admin.vouchers'),
    url(r'^vouchers/add$', admin.VoucherCreate.as_view(), name='admin.vouchers.add'),
    url(r'^vouchers/(?P<voucher>\d+)/$', admin.VoucherUpdate.as_view(), name='admin.voucher'),
    url(r'^vouchers/(?P<voucher>\d+)/delete$', admin.VoucherDelete.as_view(), name='admin.voucher.delete'),
    url(r'^global/sso/$', global_settings.SSOView.as_view(), name='admin.global.sso'),
    url(
        r'^global/sso/(?P<pk>\d+)/delete/$',
        global_settings.DeleteOAuthApplicationView.as_view(),
        name='admin.global.sso.delete',
    ),
    url(r'^pages/$', pages.PageList.as_view(), name='admin.pages'),
    url(r'^pages/add$', pages.PageCreate.as_view(), name='admin.pages.add'),
    url(r'^pages/(?P<id>\d+)/edit$', pages.PageUpdate.as_view(), name='admin.pages.edit'),
    url(r'^pages/(?P<id>\d+)/delete$', pages.PageDelete.as_view(), name='admin.pages.delete'),
    path('config/', admin.SystemConfigView.as_view(), name='admin.config'),
    path('update/', admin.UpdateCheckView.as_view(), name='admin.update'),
    path('video/', include(('eventyay.control.video.urls', 'video_admin'))),
]
