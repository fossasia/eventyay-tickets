from django.urls import reverse
from jinja2 import pass_context
from jinja2.runtime import Context


# Ref: https://github.com/niwinz/django-jinja/blob/master/django_jinja/builtins/extensions.py#L173
@pass_context
def url_for(context: Context, name: str, *args, query_string=None, **kwargs):
    try:
        current_app = context['request'].current_app
    except KeyError:
        current_app = None
    except AttributeError:
        try:
            current_app = context['request'].resolver_match.namespace
        except AttributeError:
            current_app = None
    base_url = reverse(name, args=args, kwargs=kwargs, current_app=current_app)
    return '{}?{}'.format(base_url, query_string) if query_string else base_url
