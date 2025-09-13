from django.conf import settings
from django.http import FileResponse, Http404


def is_form_bound(request, form_name, form_param='form'):
    return request.method == 'POST' and request.POST.get(form_param) == form_name


def get_static(request, path, content_type):  # pragma: no cover
    path = settings.BASE_DIR / 'static' / path
    if not path.exists():
        raise Http404()
    return FileResponse(open(path, 'rb'), content_type=content_type, as_attachment=False)
