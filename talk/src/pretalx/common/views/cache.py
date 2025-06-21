import hashlib

from django.core.cache import caches
from django.http import HttpResponse, HttpResponseNotModified
from django.utils.cache import (
    get_cache_key,
    has_vary_header,
    learn_cache_key,
    patch_response_headers,
)
from django.views.decorators.cache import cache_page


def get_requested_etag(request):
    """Return the ETag requested by the client, or None if not found."""
    if if_none_match := request.headers.get("If-None-Match"):
        return if_none_match.strip('"')


def get_etag(response):
    content = response.content
    if isinstance(content, str):
        content = content.encode()
    return hashlib.md5(content).hexdigest()


def conditional_cache_page(
    timeout,
    *,
    cache=None,
    key_prefix=None,
    condition=None,
    server_timeout=None,
    headers=None,
):
    """This decorator wraps Django's cache_page decorator, and adds some features:

    - The option to skip caching entirely based on a condition.
      If the condition function returns False, the page will not be cached at all.
    - Allow the response to be cached for a different amount of time on the server
      than we tell to the client (useful because we can invalidate the cache).
    - Calculate an ETag based on the response content, and cache it along with the
      cached response. If an ETag is requested, but not found in the cache, the
      response will be recalculated and cached with the ETag.
    """

    def decorator(func):
        def wrapper(request, *args, **kwargs):
            if request.method != "GET":
                return func(request, *args, **kwargs)
            if condition and not condition(request, *args, **kwargs):
                return func(request, *args, **kwargs)

            return etag_cache_page(
                timeout,
                cache_alias=cache,
                key_prefix=key_prefix,
                server_timeout=server_timeout,
                request=request,
                request_args=args,
                request_kwargs=kwargs,
                handler=func,
                headers=headers,
            )

        return wrapper

    return decorator


def should_cache(request, response):
    if response.streaming or response.status_code not in (200, 304):
        return False
    if not request.COOKIES and response.cookies and has_vary_header(response, "Cookie"):
        return False
    # Don't cache a response with 'Cache-Control: private'
    if "private" in response.get("Cache-Control", ()):
        return False
    return True


def patched_response(response, timeout, headers=None):
    patch_response_headers(response, timeout)
    if headers:
        for key, value in headers.items():
            response[key] = value
    return response


def etag_cache_page(
    timeout,
    *,
    cache_alias=None,
    key_prefix=None,
    server_timeout=None,
    request=None,
    request_args=None,
    request_kwargs=None,
    handler=None,
    headers=None,
):
    server_timeout = server_timeout or timeout
    requested_etag = get_requested_etag(request)
    if callable(key_prefix):
        key_prefix = key_prefix(request, *request_args, **request_kwargs)

    cache = caches[cache_alias or "default"]
    cache_key = get_cache_key(request, key_prefix, "GET", cache=cache_alias)
    etag_suffix = "_etag"
    current_etag = cache.get(f"{cache_key}{etag_suffix}") if cache_key else None

    if current_etag and requested_etag and current_etag != requested_etag:
        current_etag = None
    elif requested_etag and current_etag == requested_etag:
        return patched_response(HttpResponseNotModified(), timeout, headers=headers)

    if cache_key and (cached_response := cache.get(cache_key)):
        return patched_response(HttpResponse(cached_response), timeout, headers=headers)
    else:
        response = cache_page(
            timeout=server_timeout, cache=cache_alias, key_prefix=key_prefix
        )(handler)(request, *request_args, **request_kwargs)
        if not should_cache(request, response):
            return patched_response(response, timeout, headers=headers)

    cache_key = cache_key or learn_cache_key(
        request, response, timeout, key_prefix, cache=cache_alias
    )

    if not current_etag:
        current_etag = get_etag(response)
        cache.set(f"{cache_key}{etag_suffix}", current_etag, timeout=server_timeout)

    # If an ETag was requested and we forgot about it, but now our response matches the
    # requested ETag, return 304
    if requested_etag and current_etag == requested_etag:
        return patched_response(HttpResponseNotModified(), timeout, headers=headers)

    response["ETag"] = f'"{current_etag}"'
    return patched_response(response, timeout, headers=headers)
