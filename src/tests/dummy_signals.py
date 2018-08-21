from django.dispatch import receiver

from pretalx.cfp.signals import footer_link


@receiver(footer_link)
def footer_link_test(sender, request, **kwargs):
    link = f'/{request.event.slug}/test' if hasattr(request, 'event') else '/test'
    return {'link': link, 'label': 'test'}
