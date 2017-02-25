from django.conf import settings
from django.conf.urls import include, url

from pretalx.person.views import auth

auth_urls = [
    url('^login/$', auth.LoginView.as_view(), name='login'),
    url('^logout/$', auth.logout_view, name='logout'),
]
