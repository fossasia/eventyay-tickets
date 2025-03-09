from django import template
from django.urls import reverse
from django.utils.http import urlencode

register = template.Library()


@register.simple_tag(takes_context=True)
def build_login_url(context):
    request = context["request"]
    next_path = request.path
    query_string = request.META.get("QUERY_STRING", "")

    # Construct the base login URL
    login_url = reverse("control:auth.login")

    # Encode the next parameter
    if query_string:
        next_param = f"{next_path}?{query_string}"
    else:
        next_param = next_path

    # Full login URL with the encoded next parameter
    full_url = f"{login_url}?{urlencode({'next': next_param})}"

    return full_url
