from django.dispatch import receiver

from pretalx.cfp.signals import footer_link


@receiver(footer_link)
def footer_link_test(sender, request, **kwargs):
    event = getattr(request, "event", None)
    link = f'/{event.slug}/test' if event else '/test'
    return {'link': link, 'label': 'test'}
