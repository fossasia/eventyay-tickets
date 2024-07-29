from allauth.socialaccount.models import SocialApp
from django import forms
from django.conf import settings
from django.contrib.sites.models import Site


class SSOClientForm(forms.ModelForm):
    def __init__(self, provider_id, *args, **kwargs):
        social_app = SocialApp.objects.filter(provider=provider_id).first()
        kwargs["instance"] = social_app
        super().__init__(*args, **kwargs)
        self.fields['secret'].required = True  # Secret is required

    class Meta:
        model = SocialApp
        fields = ["client_id", "secret"]

    def save(self, organiser=None):
        self.instance.name = organiser
        self.instance.provider = organiser
        super().save()
        self.instance.sites.add(Site.objects.get(pk=settings.SITE_ID))
