from pretalx.common.templatetags.rich_text import rich_text


class CfPFormMixin:
    """All forms used in the CfP step process should use this mixin.

    It serves to make it work with the CfP Flow editor, e.g. by allowing
    users to change help_text attributes of fields. Needs to go first
    before all other forms changing help_text behaviour.
    """

    def _update_cfp_texts(self, field_name):
        field = self.fields.get(field_name)
        if not field or not self.field_configuration:
            return
        field_data = self.field_configuration.get(field_name) or {}
        field.original_help_text = field_data.get("help_text") or ""
        if field.original_help_text:
            field.help_text = rich_text(
                str(field.original_help_text)
                + " "
                + str(getattr(field, "added_help_text", ""))
            )
        if field_data.get("label"):
            field.label = field_data["label"]

    def __init__(self, *args, field_configuration=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.field_configuration = field_configuration
        if self.field_configuration:
            self.field_configuration = {
                field_data["key"]: field_data for field_data in field_configuration
            }
            for field_data in self.field_configuration:
                if field_data in self.fields:
                    self._update_cfp_texts(field_data)
