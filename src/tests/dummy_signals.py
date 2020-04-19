from django.dispatch import receiver

from pretalx.cfp.signals import footer_link, html_above_profile_page, html_head


@receiver(footer_link)
def footer_link_test(sender, request, **kwargs):
    event = getattr(request, "event", None)
    link = f"/{event.slug}/test" if event else "/test"
    return [{"link": link, "label": "test"}]


@receiver(html_head)
def html_head_test(sender, request, **kwargs):
    return '<meta property="pretalx:foo" content="bar">'


@receiver(html_head)
def html_above_profile_page_test(sender, request, **kwargs):
    return "<p></p>"
