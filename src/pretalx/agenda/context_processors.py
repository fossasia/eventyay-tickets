
def is_html_export(request):
    context = {'is_html_export': request.META.get('is_html_export') is True}
    return context
