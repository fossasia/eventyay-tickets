from django.conf import settings

from pretix.base.models import User
from pretix.control.views.auth import process_login_and_set_cookie


def oauth_return(request):
    user = User.objects.filter(email=request.user.email).first()
    if not user:
        locale = (
            request.LANGUAGE_CODE
            if hasattr(request, 'LANGUAGE_CODE')
            else settings.LANGUAGE_CODE
        )
        timezone = (
            request.timezone if hasattr(request, 'timezone') else settings.TIME_ZONE
        )
        user = User.objects.create(
            email=request.user.email,
            locale=locale,
            timezone=timezone,
            auth_backend='native',
            password='',
        )

    return process_login_and_set_cookie(request, user, False)
