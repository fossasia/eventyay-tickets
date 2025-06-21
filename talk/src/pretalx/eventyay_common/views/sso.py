from allauth.socialaccount.models import SocialApp
from django.conf import settings
from django.contrib import messages
from django.contrib.sites.models import Site
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView

from pretalx.common.text.phrases import phrases
from pretalx.common.views import CreateOrUpdateView
from pretalx.common.views.mixins import ActionConfirmMixin, PermissionRequired
from pretalx.orga.forms.sso_client_form import SSOClientForm


class SSOConfigureView(PermissionRequired, CreateOrUpdateView):
    template_name = "eventyay_common/sso/detail.html"
    permission_required = "person.is_administrator"
    form_class = SSOClientForm
    model = SocialApp

    def get_object(self):
        """
        Get the SocialApp instance for the 'eventyay' provider if it exists.
        If not, return None to create a new instance.
        Note: "eventyay" is the provider name for the Eventyay Ticket Provider.
        """
        return SocialApp.objects.filter(provider=settings.EVENTYAY_SSO_PROVIDER).first()

    def get_success_url(self):
        messages.success(self.request, phrases.base.saved)
        return self.request.path

    def form_valid(self, form):
        """
        Handle the form submission and save the instance.
        """
        instance = form.save(commit=False)
        instance.provider = settings.EVENTYAY_SSO_PROVIDER
        instance.name = "Eventyay Ticket Provider"
        with transaction.atomic():
            instance.save()
            site = Site.objects.get(pk=settings.SITE_ID)
            instance.sites.add(site)
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        """
        Handle invalid form submissions.
        """
        messages.error(
            self.request,
            "There was an error updating the Eventyay Ticket "
            "Provider configuration.",
        )
        return self.render_to_response(self.get_context_data(form=form))

    def get_context_data(self, **kwargs):
        """
        Add additional context to the template if necessary.
        """
        context = super().get_context_data(**kwargs)
        context["sso_provider"] = self.get_object()
        return context


class SSODeleteView(PermissionRequired, ActionConfirmMixin, DetailView):
    permission_required = "person.is_administrator"
    model = SocialApp
    action_text = (
        _("You will not able to login with eventyay-tickets account.")
        + " "
        + phrases.base.delete_warning
    )

    def get_object(self, queryset=None):
        return SocialApp.objects.filter(provider=settings.EVENTYAY_SSO_PROVIDER).first()

    def action_object_name(self):
        return _("SSO Provider") + f": {self.get_object().name}"

    @property
    def action_back_url(self):
        return reverse("orga:admin.sso.settings")

    def post(self, *args, **kwargs):
        sso_provider = self.get_object()
        sso_provider.delete()
        return HttpResponseRedirect(reverse("orga:admin.sso.settings"))
