from django.conf.urls import url

from .views import event

cfp_urls = [
    url('^$', event.EventStartpage.as_view(), name='startpage'),
]
