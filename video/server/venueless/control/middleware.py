from django.contrib.auth.middleware import (
    AuthenticationMiddleware as DjAuthenticationMiddleware,
)
from django.contrib.messages.middleware import MessageMiddleware as DjMessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware as DjSessionMiddleware


class ControlMiddleware:
    def __call__(self, request):

        if request.path.startswith("/control/"):  # Namespaces aren't set in error views
            return super().__call__(request)
        return self.get_response(request)


class SessionMiddleware(ControlMiddleware, DjSessionMiddleware):
    pass


class AuthenticationMiddleware(ControlMiddleware, DjAuthenticationMiddleware):
    pass


class MessageMiddleware(ControlMiddleware, DjMessageMiddleware):
    pass
