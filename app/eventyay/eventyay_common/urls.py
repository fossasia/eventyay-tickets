from django.urls import path
from django.views.generic import TemplateView

from eventyay.eventyay_common.views import auth

app_name = 'eventyay_common'


class DashboardView(TemplateView):
    template_name = 'pretixpresale/index.html'


urlpatterns = [
    path('logout/', auth.logout, name='auth.logout'),
    path('login/', auth.login, name='auth.login'),
    path('login/2fa/', auth.Login2FAView.as_view(), name='auth.login.2fa'),
    path('register/', auth.register, name='auth.register'),
    path('forgot/', auth.Forgot.as_view(), name='auth.forgot'),
    path('forgot/recover/', auth.Recover.as_view(), name='auth.forgot.recover'),
    path('', DashboardView.as_view(), name='dashboard'),
]
