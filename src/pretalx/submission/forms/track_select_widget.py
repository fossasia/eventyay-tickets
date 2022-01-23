from django import forms


class TrackSelectWidget(forms.Select):
    template_name = "widgets/track-select-widget.html"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        queryset = self.choices.queryset
        has_descriptions = any(track.description for track in queryset)

        context["tracks"] = queryset
        context["has_descriptions"] = has_descriptions
        return context

    def create_option(
        self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        option = super().create_option(
            name, value, label, selected, index, subindex, attrs
        )
        if value:
            queryset = self.choices.queryset
            track = next(track for track in queryset if track.id == value)
            description = str(track.description)
            if description:
                option["attrs"]["data-description"] = description

        return option
