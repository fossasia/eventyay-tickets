class ReadOnlyFlag:
    def __init__(self, *args, read_only=False, **kwargs):
        super().__init__(*args, **kwargs)
        if read_only:
            for field_name, field in self.fields.items():
                field.disabled = True
