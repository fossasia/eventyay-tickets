from django import template
from allauth.socialaccount.models import SocialApp

register = template.Library()

@register.simple_tag
def socialapp_exists(provider):
    return SocialApp.objects.filter(provider=provider).exists()
