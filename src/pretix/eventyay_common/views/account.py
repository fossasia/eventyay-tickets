from django.urls import reverse

from pretix.control.views.user import UserSettings
from ..navigation import get_account_navigation


class AccountSettings(UserSettings):
    template_name = 'eventyay_common/account/settings.html'

    def get_success_url(self):
        return reverse('eventyay_common:account')


class AccountGeneralSettings(UserSettings):
    template_name = 'eventyay_common/account/settings.html'

    def get_success_url(self):
        return reverse('eventyay_common:account')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['nav_items'] = get_account_navigation(self.request)
        return ctx
        
    