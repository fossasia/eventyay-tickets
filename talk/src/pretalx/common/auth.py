from contextlib import suppress

from django.contrib.auth import authenticate
from django.core.exceptions import MultipleObjectsReturned

from pretalx.person.models import User


class AuthenticationTokenBackend:
    def authenticate(self, *args, token=None, **kwargs):
        if token:
            with suppress(User.DoesNotExist, MultipleObjectsReturned):
                return User.objects.get(auth_token__key__iexact=token)
        return None


class AuthenticationTokenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated and "Authorization" in request.headers:
            token = request.headers["Authorization"].lower()
            token = token[len("token ") :] if token.startswith("token ") else token
            user = authenticate(
                request,
                token=token,
                backend="pretalx.common.auth.AuthenticationTokenBackend",
            )
            if user:
                request.user = user
        return self.get_response(request)
