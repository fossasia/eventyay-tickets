import os.path
from contextlib import suppress

from django.conf import settings
from django.http import FileResponse, Http404
from django.views.generic.detail import SingleObjectTemplateResponseMixin
from django.views.generic.edit import ModelFormMixin, ProcessFormView


class CreateOrUpdateView(
    SingleObjectTemplateResponseMixin, ModelFormMixin, ProcessFormView
):
    def set_object(self):
        if getattr(self, 'object', None) is None:
            setattr(self, 'object', None)
        with suppress(self.model.DoesNotExist, AttributeError):
            setattr(self, 'object', self.get_object())

    def get(self, request, *args, **kwargs):
        self.set_object()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.set_object()
        return super().post(request, *args, **kwargs)


def is_form_bound(request, form_name, form_param='form'):
    return request.method == 'POST' and request.POST.get(form_param) == form_name


def get_static(request, path, content_type):
    """TODO: move to staticfiles usage as per https://gist.github.com/SmileyChris/8d472f2a67526e36f39f3c33520182bc
    This would avoid potential directory traversal by … a malicious urlconfig, so not a huge attack vector."""
    path = os.path.join(settings.BASE_DIR, 'pretalx/static', path)
    if not os.path.exists(path):
        raise Http404()
    return FileResponse(open(path, 'rb'), content_type=content_type)
