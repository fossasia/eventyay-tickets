from django.conf import settings
from django.contrib import messages
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView

from pretix.control.permissions import AdministratorPermissionRequiredMixin
from pretix.eventyay_common.forms.page import PageSettingsForm


class PageCreate(AdministratorPermissionRequiredMixin, FormView):
    template_name = 'eventyay_common/pages/form.html'
    form_class = PageSettingsForm

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["locales"] = [
            locale for locale in settings.LANGUAGES
        ]
        return ctx

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes have not been saved, see below for errors.'))
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse('eventyay_common:pages.create')
