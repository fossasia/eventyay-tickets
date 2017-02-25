from django.conf.urls import url

from .views import auth, dashboard, event

orga_urls = [
    url('^login/$', auth.LoginView.as_view(), name='login'),
    url('^logout/$', auth.logout_view, name='logout'),
    url('^event/new/', event.EventCreate.as_view(), name='event.create'),
    url('^event/(?P<event>\w+)/', event.EventDetail.as_view(), name='event.view'),
    url('^$', dashboard.DashboardView.as_view(), name='dashboard'),
]
