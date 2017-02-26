from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.urlresolvers import reverse
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, DetailView, UpdateView

from pretalx.orga.authorization import OrgaPermissionRequired
from pretalx.orga.forms import CfPForm
from pretalx.person.models import User
from pretalx.submission.models import CfP


class CfPDetail(OrgaPermissionRequired, UpdateView):
    form_class = CfPForm
    model = CfP
    slug_url_kwarg = 'event'
    slug_field = 'slug'
    template_name = 'orga/cfp/form.html'

    def get_object(self):
        return self.request.event.get_cfp()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['read_only'] = True
        return kwargs

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['action'] = 'view'
        return context


class CfPUpdate(OrgaPermissionRequired, UpdateView):
    model = CfP
    slug_url_kwarg = 'event'
    slug_field = 'slug'
    form_class = CfPForm
    template_name = 'orga/cfp/form.html'

    def get_object(self):
        return self.request.event.get_cfp()

    def get_success_url(self) -> str:
        return reverse('orga:cfp.view', kwargs={'event': self.object.event.slug})

    def form_valid(self, form):
        messages.success(self.request, 'Yay!')
        form.instance.event = self.request.event
        ret = super().form_valid(form)
        return ret

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['action'] = 'update'
        return context
