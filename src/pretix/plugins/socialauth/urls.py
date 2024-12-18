from django.urls import re_path as url

from . import views

urlpatterns = [
    url(r'^oauth_login/(?P<provider>[a-zA-Z]+)/$', views.oauth_login, name='social.oauth.login'),
    url(r'^oauth_return$', views.oauth_return, name='social.oauth.return')
]
