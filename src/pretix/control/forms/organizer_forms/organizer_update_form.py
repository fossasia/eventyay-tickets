from urllib.parse import urlparse

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from pretix.multidomain.models import KnownDomain

from .organizer_form import OrganizerForm


class OrganizerUpdateForm(OrganizerForm):

    def __init__(self, *args, **kwargs):
        self.domain = kwargs.pop("domain", False)
        self.change_slug = kwargs.pop("change_slug", False)
        kwargs.setdefault("initial", {})
        self.instance = kwargs["instance"]
        if self.domain and self.instance:
            initial_domain = self.instance.domains.filter(event__isnull=True).first()
            if initial_domain:
                kwargs["initial"].setdefault("domain", initial_domain.domainname)

        super().__init__(*args, **kwargs)
        if not self.change_slug:
            self.fields["slug"].widget.attrs["readonly"] = "readonly"
        if self.domain:
            self.fields["domain"] = forms.CharField(
                max_length=255,
                label=_("Custom domain"),
                required=False,
                help_text=_(
                    "You need to configure the custom domain in the webserver beforehand."
                ),
            )

    def clean_domain(self):
        d = self.cleaned_data["domain"]
        if d:
            if d == urlparse(settings.SITE_URL).hostname:
                raise ValidationError(
                    _("You cannot choose the base domain of this installation.")
                )
            if (
                KnownDomain.objects.filter(domainname=d)
                .exclude(organizer=self.instance.pk, event__isnull=True)
                .exists()
            ):
                raise ValidationError(
                    _(
                        "This domain is already in use for a different event or organizer."
                    )
                )
        return d

    def clean_slug(self):
        if self.change_slug:
            return self.cleaned_data["slug"]
        return self.instance.slug

    def save(self, commit=True):
        instance = super().save(commit)

        if self.domain:
            current_domain = instance.domains.first()
            if self.cleaned_data["domain"]:
                if (
                    current_domain
                    and current_domain.domainname != self.cleaned_data["domain"]
                ):
                    current_domain.delete()
                    KnownDomain.objects.create(
                        organizer=instance, domainname=self.cleaned_data["domain"]
                    )
                elif not current_domain:
                    KnownDomain.objects.create(
                        organizer=instance, domainname=self.cleaned_data["domain"]
                    )
            elif current_domain:
                current_domain.delete()
            instance.cache.clear()
            for ev in instance.events.all():
                ev.cache.clear()

        return instance
