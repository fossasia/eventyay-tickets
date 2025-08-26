import logging
import urllib.parse

from django.core import signing
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
)
from django.shortcuts import render
from django.urls import reverse

logger = logging.getLogger(__name__)


def _is_samesite_referer(request: HttpRequest) -> bool:
    referer = request.headers.get('referer')
    if referer is None:
        return False

    referer = urllib.parse.urlparse(referer)

    # Make sure we have a valid URL for Referer.
    if '' in (referer.scheme, referer.netloc):
        return False

    return (referer.scheme, referer.netloc) == (request.scheme, request.get_host())


def redirect_view(request: HttpRequest) -> HttpResponse:
    signer = signing.Signer(salt='safe-redirect')
    try:
        url = signer.unsign(request.GET.get('url', ''))
    except signing.BadSignature:
        return HttpResponseBadRequest('Invalid parameter')

    if not _is_samesite_referer(request):
        u = urllib.parse.urlparse(url)
        return render(
            request,
            'common/redirect.html',
            {
                'hostname': u.hostname,
                'url': url,
            },
        )
    return HttpResponseRedirect(url)


def safelink(url: str) -> str:
    """Wrap a URL with our redirect view to check if the user is about to go to external site."""
    signer = signing.Signer(salt='safe-redirect')
    return reverse('redirect') + '?url=' + urllib.parse.quote(signer.sign(url))
