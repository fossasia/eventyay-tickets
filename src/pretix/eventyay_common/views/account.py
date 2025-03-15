from django.urls import reverse

from pretix.control.views.user import UserSettings


class AccountSettings(UserSettings):
    template_name = 'eventyay_common/account/settings.html'

    def get_success_url(self):
        return reverse('eventyay_common:account')
