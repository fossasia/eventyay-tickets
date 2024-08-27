from django.apps import AppConfig


class SSOProviderConfig(AppConfig):
    name = "pretalx.sso_provider"

    def ready(self):
        from allauth.socialaccount import providers

        from .providers import EventyayProvider

        providers.registry.register(EventyayProvider)
