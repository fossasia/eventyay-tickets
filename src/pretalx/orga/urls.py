from django.conf.urls import url

from .views import auth, cfp, dashboard, event

orga_urls = [
    url('^login/$', auth.LoginView.as_view(), name='login'),
    url('^logout/$', auth.logout_view, name='logout'),
    url('^event/new/', event.EventCreate.as_view(), name='event.create'),
    url('^event/(?P<event>\w+)/cfp/update/', cfp.CfPUpdate.as_view(), name='cfp.update'),
    url('^event/(?P<event>\w+)/cfp/', cfp.CfPDetail.as_view(), name='cfp.view'),
    url('^event/(?P<event>\w+)/update/', event.EventUpdate.as_view(), name='event.update'),
    url('^event/(?P<event>\w+)/', event.EventDetail.as_view(), name='event.view'),
    url('^$', dashboard.DashboardView.as_view(), name='dashboard'),
]
