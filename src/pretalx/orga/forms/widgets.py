from django.conf import settings
from django.forms import CheckboxSelectMultiple, RadioSelect


class HeaderSelect(RadioSelect):
    option_template_name = 'orga/widgets/header_option.html'


class MultipleLanguagesWidget(CheckboxSelectMultiple):
    option_template_name = 'orga/widgets/multi_languages_widget.html'

    def sort(self):
        self.choices = sorted(
            self.choices,
            key=lambda l: (
                (0 if l[0] in settings.LANGUAGES_OFFICIAL else 1),
                str(l[1]),
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
        attrs['lang'] = value
        opt = super().create_option(
            name, value, label, selected, index, subindex, attrs
        )
        opt['official'] = value in settings.LANGUAGES_OFFICIAL
        return opt
