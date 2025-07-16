from rest_framework import exceptions
from rest_framework.authentication import TokenAuthentication

from pretalx.person.models import UserApiToken


class UserTokenAuthentication(TokenAuthentication):
    model = UserApiToken

    def authenticate_credentials(self, key):
        model = self.get_model()
        try:
            token = (
                model.objects.active()
                .select_related("user")
                .prefetch_related("events")
                .get(token=key)
            )
        except model.DoesNotExist:
            raise exceptions.AuthenticationFailed("Invalid token.")

        if not token.is_active:
            raise exceptions.AuthenticationFailed("Token inactive or deleted.")

        return token.user, token
