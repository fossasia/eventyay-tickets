from django import forms


class ReadOnlyFlag:

    def __init__(self, *args, read_only=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.read_only = read_only
        if read_only:
            for field_name, field in self.fields.items():
                field.disabled = True

    def clean(self):
        if self.read_only:
            raise forms.ValidationError('You are not allowed to submit this data.')
        return super().clean()
