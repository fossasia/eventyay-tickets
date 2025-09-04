from django.conf import settings
from django.forms import CheckboxSelectMultiple, RadioSelect
from django.utils.translation import gettext_lazy as _


class HeaderSelect(RadioSelect):
    option_template_name = "orga/widgets/header_option.html"


class MultipleLanguagesWidget(CheckboxSelectMultiple):
    template_name = "orga/widgets/multi_languages_select.html"
    option_template_name = "orga/widgets/multi_languages_widget.html"

    def __init__(self, *args, **kwargs):
        kwargs["attrs"] = kwargs.get("attrs", {})
        kwargs["attrs"]["class"] = (
            kwargs["attrs"].get("class", "") + " form-check form-check-languages"
        )
        super().__init__(*args, **kwargs)

    def sort(self):
        official_languages = [
            choice
            for choice in self.choices
            if settings.LANGUAGES_INFORMATION[choice[0]].get("official")
        ]
        inofficial_languages = [
            choice
            for choice in self.choices
            if not settings.LANGUAGES_INFORMATION[choice[0]].get("official")
        ]
        self.choices = (
            (
                "",
                official_languages,
            ),
            (
                (
                    _("Community translations"),
                    _(
                        "These translations are not maintained by the eventyay team. "
                        "We cannot vouch for their correctness, and new or recently changed features "
                        "might not be translated and will show in English instead. "
                        'You can <a href="{url}" target="_blank">contribute to the translations</a>.'
                    ),
                    "fa fa-group",
                ),
                inofficial_languages,
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
