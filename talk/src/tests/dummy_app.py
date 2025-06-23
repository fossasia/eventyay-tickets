from django.apps import AppConfig


class PluginApp(AppConfig):
    name = "tests"
    verbose_name = "test app for pretalx"

    def ready(self):
        from .dummy_signals import footer_link_test  # noqa

    def is_available(self, event):
        return event != "totally hidden"

    class PretalxPluginMeta:
        name = "test plugin for pretalx"
        author = "Tobias Kunze"
        description = "Helps to test plugin related things for pretalx"
        visible = True
        version = "0.0.0"
