from django.conf.urls import url

from .views import auth, dashboard

orga_urls = [
    url('^login/$', auth.LoginView.as_view(), name='login'),
    url('^logout/$', auth.logout_view, name='logout'),
    url('^$', dashboard.DashboardView.as_view(), name='dashboard'),
]
