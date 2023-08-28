from django.conf import settings
from django.forms import CheckboxSelectMultiple, RadioSelect


class HeaderSelect(RadioSelect):
    option_template_name = "orga/widgets/header_option.html"


class MultipleLanguagesWidget(CheckboxSelectMultiple):
    option_template_name = "orga/widgets/multi_languages_widget.html"

    def __init__(self, *args, **kwargs):
        kwargs["attrs"] = kwargs.get("attrs", {})
        kwargs["attrs"]["class"] = (
            kwargs["attrs"].get("class", "") + " form-check form-check-languages"
        )
        super().__init__(*args, **kwargs)

    def sort(self):
        self.choices = sorted(
            self.choices,
            key=lambda locale: (
                not settings.LANGUAGES_INFORMATION[locale[0]].get("official"),
                str(locale[1]),
            ),
        )

    def options(self, name, value, attrs=None):
        self.sort()
        return super().options(name, value, attrs)

    def optgroups(self, name, value, attrs=None):
        self.sort()
        return super().optgroups(name, value, attrs)

    def create_option(
        self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        attrs["lang"] = value
        opt = super().create_option(
            name, value, label, selected, index, subindex, attrs
        )
        language = settings.LANGUAGES_INFORMATION[value]
        opt["official"] = bool(language.get("official"))
        opt["percentage"] = language["percentage"]
        return opt
