from urllib.request import urlopen

import lxml.html
from django import forms
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _

from pretix.base.models.page import Page


class PageSettingsForm(forms.ModelForm):
    class Meta:
        model = Page
        fields = (
            "title",
            "slug",
            "link_on_website_start_page",
            "link_in_header",
            "link_in_footer",
            "require_confirmation",
            "text"
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    mimes = {
        "image/gif": "gif",
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }

    def clean_slug(self):
        slug = self.cleaned_data["slug"]
        if Page.objects.filter(slug=slug).exists():
            raise forms.ValidationError(
                _("You already have a page on that URL."),
                code="duplicate_slug",
            )
        return slug

    def clean_text(self):
        t = self.cleaned_data["text"]
        for locale, html in t.data.items():
            etrees = lxml.html.fragments_fromstring(html)
            t.data[locale] = ""
            for etree in etrees:
                # Find all data:-based image URLs, store them to CDN and replace the image node
                for image in etree.xpath("//img"):
                    original_image_src = image.attrib["src"]
                    if original_image_src.startswith("data:"):
                        ftype = original_image_src.split(";")[0][5:]
                        if ftype in self.mimes:
                            with urlopen(original_image_src) as response:
                                cfile = ContentFile(response.read())
                                nonce = get_random_string(length=32)
                                name = "pub/pages/img/{}.{}".format(
                                    nonce, self.mimes[ftype]
                                )
                                stored_name = default_storage.save(name, cfile)
                                stored_url = default_storage.url(stored_name)
                                image.attrib["src"] = stored_url
                t.data[locale] += lxml.html.tostring(etree).decode()
        return t
