from django.conf import settings
from django.http import (
    HttpResponsePermanentRedirect, HttpResponseRedirect, StreamingHttpResponse,
)


class ChunkBasedFileResponse(StreamingHttpResponse):
    block_size = 4096

    def __init__(self, streaming_content=(), *args, **kwargs):
        filelike = streaming_content
        streaming_content = streaming_content.chunks(self.block_size)
        super().__init__(streaming_content, *args, **kwargs)
        self['Content-Length'] = filelike.size


def get_client_ip(request):
    ip = request.META.get('REMOTE_ADDR')
    if settings.TRUST_X_FORWARDED_FOR:
        x_forwarded_for = request.headers.get('x-forwarded-for')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
    return ip


def redirect_to_url(to, permanent=False):
    redirect_class = HttpResponsePermanentRedirect if permanent else HttpResponseRedirect
    return redirect_class(to)
