import bleach
from django import forms
from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, ListView, TemplateView, UpdateView

from pretix.base.models.page import Page
from pretix.control.forms.page import PageSettingsForm
from pretix.control.permissions import AdministratorPermissionRequiredMixin
from pretix.helpers.compat import CompatDeleteView


class PageList(AdministratorPermissionRequiredMixin, ListView):
    model = Page
    context_object_name = 'pages'
    paginate_by = 20
    template_name = 'pretixcontrol/admin/pages/index.html'


class PageCreate(AdministratorPermissionRequiredMixin, FormView):
    model = Page
    template_name = 'pretixcontrol/admin/pages/form.html'
    form_class = PageSettingsForm

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['locales'] = [(locale[0], locale[1]) for locale in settings.LANGUAGES]
        return ctx

    def get_success_url(self) -> str:
        return reverse(
            'control:admin.pages',
        )

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes have not been saved, see below for errors.'))
        return super().form_invalid(form)


class PageDetailMixin:
    def get_object(self, queryset=None) -> Page:
        try:
            return Page.objects.get(id=self.kwargs['id'])
        except Page.DoesNotExist:
            raise Http404(_('The requested page does not exist.'))

    def get_success_url(self) -> str:
        return reverse(
            'control:admin.pages',
        )


class PageEditForm(PageSettingsForm):
    slug = forms.CharField(label=_('URL form'), disabled=True)

    def clean_slug(self):
        return self.instance.slug


class PageUpdate(AdministratorPermissionRequiredMixin, PageDetailMixin, UpdateView):
    model = Page
    form_class = PageEditForm
    template_name = 'pretixcontrol/admin/pages/form.html'
    context_object_name = 'page'

    def get_success_url(self) -> str:
        return reverse(
            'control:admin.pages.edit',
            kwargs={
                'id': self.object.pk,
            },
        )

    def get_text_for_language(self, lng_code: str) -> str:
        if not self.object.text or not isinstance(self.object.text.data, dict):
            return ''
        return self.object.text.data.get(lng_code, '')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        ctx['locales'] = []
        ctx['url'] = f'{settings.SITE_URL}/{settings.BASE_PATH}page/{self.object.slug}'

        for lng_code, lng_name in settings.LANGUAGES:
            ctx['locales'].append((lng_code, lng_name))
            ctx[f'text_{lng_code}'] = self.get_text_for_language(lng_code)
        return ctx

    def form_valid(self, form):
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _('We could not save your changes. See below for details.'))
        return super().form_invalid(form)


class PageDelete(AdministratorPermissionRequiredMixin, PageDetailMixin, CompatDeleteView):
    model = Page
    template_name = 'pretixcontrol/admin/pages/delete.html'
    context_object_name = 'page'

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        messages.success(request, _('The selected page has been deleted.'))
        return HttpResponseRedirect(self.get_success_url())


class ShowPageView(TemplateView):
    template_name = 'pretixcontrol/admin/pages/show.html'

    def get_page(self):
        try:
            return Page.objects.get(slug=self.kwargs['slug'])
        except Page.DoesNotExist:
            raise Http404(_('The requested page does not exist.'))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        page = self.get_page()
        ctx['page'] = page
        ctx['show_link_in_header_for_all_pages'] = Page.objects.filter(link_in_header=True)
        ctx['show_link_in_footer_for_all_pages'] = Page.objects.filter(link_in_footer=True)

        attributes = dict(bleach.ALLOWED_ATTRIBUTES)
        attributes['a'] = ['href', 'title', 'target']
        attributes['p'] = ['class']
        attributes['li'] = ['class']
        attributes['img'] = ['src']

        ctx['content'] = bleach.clean(
            str(page.text),
            tags=bleach.ALLOWED_TAGS + ['img', 'p', 'br', 's', 'sup', 'sub', 'u', 'h3', 'h4', 'h5', 'h6'],
            attributes=attributes,
            protocols=bleach.ALLOWED_PROTOCOLS + ['data'],
        )
        return ctx
