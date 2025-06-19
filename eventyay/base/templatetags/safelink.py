from django import template



from ..views.redirect import safelink as sl

def get_token(request, answer):
    if not request.session.session_key:
        request.session.create()
    payload = '{}:{}'.format(request.session.session_key, answer.pk)
    signer = TimestampSigner()
    return signer.sign(hashlib.sha1(payload.encode()).hexdigest())

register = template.Library()


@register.simple_tag
def safelink(url):
    return sl(url)


@register.simple_tag
def answer_token(request, answer):
    return get_token(request, answer)
