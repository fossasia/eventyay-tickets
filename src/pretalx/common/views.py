from contextlib import suppress

from django.views.generic.detail import SingleObjectTemplateResponseMixin
from django.views.generic.edit import ModelFormMixin, ProcessFormView


class CreateOrUpdateView(SingleObjectTemplateResponseMixin, ModelFormMixin, ProcessFormView):

    def set_object(self):
        self.object = None
        with suppress(self.model.DoesNotExist):
            self.object = self.get_object()

    def get(self, request, *args, **kwargs):
        self.set_object()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.set_object()
        return super().post(request, *args, **kwargs)


def is_form_bound(request, form_name, form_param='form'):
    return request.method == 'POST' and request.POST.get(form_param) == form_name
