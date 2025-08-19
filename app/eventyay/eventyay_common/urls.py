from django.http import HttpResponse
from django.urls import path, reverse
from django.utils.html import escape

from eventyay.eventyay_common.views import auth

app_name = 'eventyay_common'


def dashboard_view(request):
    logout_url = reverse('eventyay_common:auth.logout')
    content = f'<p>Welcome to the common dashboard. <a href="{escape(logout_url)}">Logout</a></p>'
    return HttpResponse(content)


urlpatterns = [
    path('logout/', auth.logout, name='auth.logout'),
    path('login/', auth.login, name='auth.login'),
    path('login/2fa/', auth.Login2FAView.as_view(), name='auth.login.2fa'),
    path('register/', auth.register, name='auth.register'),
    path('forgot/', auth.Forgot.as_view(), name='auth.forgot'),
    path('forgot/recover/', auth.Recover.as_view(), name='auth.forgot.recover'),
    path('', dashboard_view, name='dashboard'),
]
