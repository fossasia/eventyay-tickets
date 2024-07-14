from django.urls import path
from .views import oauth2_login, oauth2_callback


from allauth.socialaccount.providers.oauth2.urls import default_urlpatterns

from .providers import EventyayProvider

urlpatterns = default_urlpatterns(EventyayProvider)
