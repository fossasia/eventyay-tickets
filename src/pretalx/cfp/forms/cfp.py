class CfPFormMixin:
    """All forms used in the CfP step process should use this mixin.

    It serves to make it work with the CfP Flow editor, e.g. by allowing
    users to change help_text attributes of fields. Needs to go first
    before all other forms changing help_text behaviour.
    """

    def __init__(self, *args, field_configuration=None, **kwargs):
        super().__init__(*args, **kwargs)
        if field_configuration:
            for field_data in field_configuration:
                field = self.fields.get(field_data['key'])
                if not field:
                    continue
                help_text = field_data.get('help_text')
                if help_text:
                    field.help_text = str(help_text) + ' ' + str(getattr(field, 'added_help_text', ''))
