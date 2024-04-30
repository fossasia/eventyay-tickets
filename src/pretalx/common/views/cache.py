from django.views.decorators.cache import cache_page


def conditional_cache_page(
    timeout, condition, *, cache=None, key_prefix=None, cache_control=None
):
    """This decorator is exactly like cache_page, but with the option to skip
    the caching entirely.

    The second argument is a callable, ``condition``. It's given the
    request and all further arguments, and if it evaluates to a true-ish
    value, the cache is used.
    """

    def decorator(func):
        def wrapper(request, *args, **kwargs):
            if condition(request, *args, **kwargs):
                prefix = key_prefix
                if callable(prefix):
                    prefix = prefix(request, *args, **kwargs)
                response = cache_page(timeout=timeout, cache=cache, key_prefix=prefix)(
                    func
                )(request, *args, **kwargs)
                if cache_control and not cache_control(request, *args, **kwargs):
                    response.headers.pop("Expires")
                    response.headers.pop("Cache-Control")

            return func(request, *args, **kwargs)

        return wrapper

    return decorator
