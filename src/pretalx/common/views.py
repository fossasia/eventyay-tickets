from django.views.generic.detail import SingleObjectTemplateResponseMixin
from django.views.generic.edit import ModelFormMixin, ProcessFormView
from i18nfield.forms import I18nModelForm


class ActionFromUrl:
    @property
    def _action(self):
        return self.request.resolver_match.url_name.split('.')[-1]

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['action'] = self._action
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['read_only'] = (self._action == 'view')
        if hasattr(self.request, 'event') and issubclass(self.form_class, I18nModelForm):
            kwargs['locales'] = self.request.event.locales
        return kwargs


class CreateOrUpdateView(SingleObjectTemplateResponseMixin, ModelFormMixin, ProcessFormView):

    def get(self, request, *args, **kwargs):
        try:
            self.object = self.get_object()
        except self.model.DoesNotExist:
            self.object = None
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        try:
            self.object = self.get_object()
        except self.model.DoesNotExist:
            self.object = None
        return super().post(request, *args, **kwargs)
