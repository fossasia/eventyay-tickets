from django.urls import re_path as url

from . import views

urlpatterns = [
    url(r'^oauth_return$', views.oauth_return, name='mediawiki.oauth.return')
]
