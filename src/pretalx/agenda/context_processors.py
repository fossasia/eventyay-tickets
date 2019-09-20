def is_html_export(request):
    """We tell templates that they are rendering a static export the request
    META is set.

    This is safe because all incoming HTTP headers are put in META in
    the form HTTP_ORIGINAL_NAME, so that 'is_html_export' cannot be
    faked from the outside.
    """
    context = {'is_html_export': request.META.get('is_html_export') is True}
    return context
