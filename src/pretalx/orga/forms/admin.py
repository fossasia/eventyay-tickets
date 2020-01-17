from django import forms
from django.utils.translation import gettext_lazy as _
from hierarkey.forms import HierarkeyForm

from pretalx.common.models.settings import GlobalSettings


class GlobalSettingsForm(HierarkeyForm):
    def __init__(self, *args, **kwargs):
        self.obj = GlobalSettings()
        super().__init__(*args, obj=self.obj, attribute_name="settings", **kwargs)


class UpdateSettingsForm(GlobalSettingsForm):
    update_check_enabled = forms.BooleanField(
        required=False,
        label=_("Perform update checks"),
        help_text=_(
            "During the update check, pretalx will report an anonymous, unique installation ID, "
            "the current version of pretalx and your installed plugins and the number of active and "
            "inactive events in your installation to servers operated by the pretalx developers. We "
            "will only store anonymous data, never any IP addresses and we will not know who you are "
            "or where to find your instance. You can disable this behavior here at any time."
        ),
    )
    update_check_email = forms.EmailField(
        required=False,
        label=_("E-mail notifications"),
        help_text=_(
            "We will notify you at this address if we detect that a new update is available. This "
            "address will not be transmitted to pretalx.com, the emails will be sent by your server "
            "locally."
        ),
    )
