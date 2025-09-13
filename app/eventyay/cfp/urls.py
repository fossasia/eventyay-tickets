from django.urls import include, path
from django.views.generic import RedirectView

from .views import auth, event

app_name = 'cfp'
urlpatterns = [
    path(
        '<slug:event>/',
        include(
            [
                path('', event.EventStartpage.as_view(), name='event.landing'),
                path(
                    'invite/<token>',
                    auth.RecoverView.as_view(is_invite=True),
                    name='event.new_recover',
                ),
                path('cfp', event.EventCfP.as_view(), name='event.start'),
            ]
        ),
    )
]
