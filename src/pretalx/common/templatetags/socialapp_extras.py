from allauth.socialaccount.models import SocialApp
from django import template

register = template.Library()


@register.simple_tag
def socialapp_exists(provider):
    return SocialApp.objects.filter(provider=provider).exists()
