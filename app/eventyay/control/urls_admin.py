from django.urls import include
from django.urls import re_path as url
from django.urls import path
from django.views.generic.base import RedirectView

from eventyay.control.views import (
    admin,
    global_settings,
    gmail_oauth,
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
    path('events/startpage-toggle/', admin.AdminEventStartpageToggle.as_view(), name='admin.events.startpage.toggle'),
    path('attendees/', admin.AttendeeListView.as_view(), name='admin.attendees'),
    path('submissions/', admin.SubmissionListView.as_view(), name='admin.submissions'),
    path('orders/', admin.AdminOrderListView.as_view(), name='admin.orders'),
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
    path('global/ticketing/', global_settings.GlobalTicketingSettingsView.as_view(), name='admin.global.ticketing'),
    path('global/business/', global_settings.GlobalBusinessSettingsView.as_view(), name='admin.global.business'),
    path('global/settings/preview/', global_settings.GlobalSettingsPagePreviewView.as_view(), name='admin.global.settings.preview'),
    path('global/settings/test-email/', global_settings.GlobalSettingsTestEmailView.as_view(), name='admin.global.settings.test_email'),
    path('global/metadata/', global_settings.MetaDataSettingsView.as_view(), name='admin.global.metadata'),

    path('global/gmail/connect/', gmail_oauth.GmailOAuthConnectView.as_view(), name='admin.global.gmail.connect'),
    path('global/gmail/callback/', gmail_oauth.GmailOAuthCallbackView.as_view(), name='admin.global.gmail.callback'),
    path('global/gmail/disconnect/', gmail_oauth.GmailOAuthDisconnectView.as_view(), name='admin.global.gmail.disconnect'),

    path('global/plugins/', global_settings.GlobalPluginManagementView.as_view(), name='admin.global.plugins'),
    path('global/update/', global_settings.UpdateRedirectView.as_view(), name='admin.global.update'),
    url(r'^global/message/$', global_settings.MessageView.as_view(), name='admin.global.message'),
    url(r'^vouchers/$', admin.VoucherList.as_view(), name='admin.vouchers'),
    url(r'^vouchers/add$', admin.VoucherCreate.as_view(), name='admin.vouchers.add'),
    url(r'^vouchers/(?P<voucher>\d+)/$', admin.VoucherUpdate.as_view(), name='admin.voucher'),
    url(r'^vouchers/(?P<voucher>\d+)/detail$', admin.VoucherDetail.as_view(), name='admin.voucher.detail'),
    url(r'^vouchers/(?P<voucher>\d+)/delete$', admin.VoucherDelete.as_view(), name='admin.voucher.delete'),
    url(r'^vouchers/(?P<voucher>\d+)/disable$', admin.VoucherDisable.as_view(), name='admin.voucher.disable'),
    url(r'^vouchers/(?P<voucher>\d+)/duplicate$', admin.VoucherDuplicate.as_view(), name='admin.voucher.duplicate'),
    url(r'^global/sso/$', global_settings.SSOView.as_view(), name='admin.global.sso'),
    url(
        r'^global/sso/(?P<pk>\d+)/delete/$',
        global_settings.DeleteOAuthApplicationView.as_view(),
        name='admin.global.sso.delete',
    ),
    url(r'^pages/$', pages.PagesStartPageView.as_view(), name='admin.pages'),
    path('pages/footer/', pages.PagesFooterView.as_view(), name='admin.pages.footer'),
    path('pages/banner/', pages.PagesGlobalBannerView.as_view(), name='admin.pages.banner'),
    path('pages/additional/', pages.PageList.as_view(), name='admin.pages.additional'),
    path('pages/content/<slug:slug>/', pages.PagesDefaultPageView.as_view(), name='admin.pages.default'),
    path('pages/locale/remove/', pages.PagesLocaleRemoveView.as_view(), name='admin.pages.locale.remove'),
    # Legacy redirect so existing /admin/startpage/ bookmarks still work.
    path('startpage/', RedirectView.as_view(pattern_name='eventyay_admin:admin.pages', permanent=True), name='admin.startpage'),
    url(r'^pages/add$', pages.PageCreate.as_view(), name='admin.pages.add'),
    path('pages/<int:id>/toggle/<str:scope>/', pages.PageVisibilityToggle.as_view(), name='admin.pages.toggle'),
    url(r'^pages/(?P<id>\d+)/edit$', pages.PageUpdate.as_view(), name='admin.pages.edit'),
    url(r'^pages/(?P<id>\d+)/delete$', pages.PageDelete.as_view(), name='admin.pages.delete'),
    path('config/', admin.SystemConfigView.as_view(), name='admin.config'),
    path('update/', admin.UpdateCheckView.as_view(), name='admin.update'),
    path('video/', include(('eventyay.control.video.urls', 'video_admin'))),
]
