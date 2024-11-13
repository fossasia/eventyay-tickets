from collections import OrderedDict
from urllib.request import urlopen

import lxml.html
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from i18nfield.forms import I18nFormField, I18nTextarea, I18nTextInput

from pretix.base.forms import SettingsForm
from pretix.base.settings import GlobalSettingsObject


class PageSettingsForm(SettingsForm):

    page_name = None

    def __init__(self, *args, **kwargs):
        self.obj = GlobalSettingsObject()
        self.page_name = kwargs.pop('page', None)
        super().__init__(*args, obj=self.obj, **kwargs)

        self.fields = OrderedDict(list(self.fields.items()) + [
            (f'{self.page_name}_title', I18nFormField(
                widget=I18nTextInput,
                required=True,
                label=_("Page title"),
                help_text=_("")
            )),
            (f'{self.page_name}_content', I18nFormField(
                widget=I18nTextarea,
                required=True,
                label=_("Page content"),
                help_text=_("")
            )),
        ])

    mimes = {
        "image/gif": "gif",
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }

    def clean(self):
        data = super().clean()
        if self.page_name:
            content_field = f"{self.page_name}_content"
            if content_field in self.cleaned_data:
                data[content_field] = self._clean_content_field(content_field)

        settings_dict = self.obj.settings.freeze()
        settings_dict.update(data)
        return data

    def _clean_content_field(self, content_field):
        page_content = self.cleaned_data[content_field]

        for locale, html_content in page_content.data.items():
            fragments = lxml.html.fragments_fromstring(html_content)
            updated_content = ""

            for fragment in fragments:
                images = fragment.xpath("//img[@src]")
                for img in images:
                    image_src = img.attrib["src"]
                    if image_src.startswith("data:"):
                        stored_url = self._store_image(image_src)
                        if stored_url:
                            img.attrib["src"] = stored_url

                updated_content += lxml.html.tostring(fragment).decode()

            page_content.data[locale] = updated_content

        return page_content

    def _store_image(self, image_src):
        """Helper method to handle the storage of data URI images."""
        ftype = image_src.split(";")[0][5:]
        if ftype in self.mimes:
            with urlopen(image_src) as response:
                content_file = ContentFile(response.read())
                nonce = get_random_string(length=32)
                name = f"pub/eventyay_common/pages/img/{nonce}.{self.mimes[ftype]}"
                stored_name = default_storage.save(name, content_file)
                return default_storage.url(stored_name)
        return None
