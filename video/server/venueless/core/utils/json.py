from django.core.serializers.json import DjangoJSONEncoder

from venueless.core.permissions import Permission


class CustomJSONEncoder(DjangoJSONEncoder):
    def default(self, o):
        if isinstance(o, Permission):
            return o.value
        elif isinstance(o, set):
            return list(o)
        else:
            return super().default(o)
