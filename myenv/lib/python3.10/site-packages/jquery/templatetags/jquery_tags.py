from django.conf import settings
from django.forms.utils import flatatt
from django.template import Library

from ..utils import jquery_path

register = Library()


@register.simple_tag
def jquery_script():
    return '<script{0}></script>'.format(flatatt({
        'type': 'text/javascript',
        'src': settings.STATIC_URL + jquery_path,
    }))
