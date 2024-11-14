import bleach
from django.conf import settings
from django.contrib import messages
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, TemplateView
from i18nfield.strings import LazyI18nString

from pretix.base.settings import GlobalSettingsObject
from pretix.control.permissions import AdministratorPermissionRequiredMixin
from pretix.eventyay_common.forms.page import PageSettingsForm


class PageCreate(AdministratorPermissionRequiredMixin, FormView):
    template_name = 'eventyay_common/pages/form.html'
    form_class = PageSettingsForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['page'] = self.kwargs.get("page")
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["locales"] = [
            locale for locale in settings.LANGUAGES
        ]
        page_name = self.kwargs.get('page')
        ctx["page_name"] = page_name
        page_titles = {
            'faq': _('FAQ settings'),
            'pricing': _('Pricing settings'),
            'privacy': _('Privacy settings'),
            'terms': _('Terms settings'),
        }
        ctx["page_title"] = page_titles.get(page_name, _('Page settings'))

        field_title = f"{page_name}_title"
        field_content = f"{page_name}_content"
        if field_title in self.get_form().fields:
            ctx["dynamic_field_title"] = self.get_form()[field_title]
        if field_content in self.get_form().fields:
            ctx["dynamic_field_content"] = self.get_form()[field_content]
        return ctx

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes have not been saved, see below for errors.'))
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse('control:admin.pages.create', kwargs={
            'page': self.kwargs.get("page")
        })


class ShowPageView(TemplateView):
    template_name = 'eventyay_common/pages/show.html'

    def get_page(self, page):
        gs = GlobalSettingsObject()
        return gs.settings.get(page + "_title"), gs.settings.get(page + "_content")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        page_title, page_content = self.get_page(page=kwargs.get("page"))
        ctx["page_title"] = str(LazyI18nString(page_title))

        attributes = dict(bleach.ALLOWED_ATTRIBUTES)
        attributes["a"] = ["href", "title", "target"]
        attributes["p"] = ["class"]
        attributes["li"] = ["class"]
        attributes["img"] = ["src"]

        ctx["content"] = bleach.clean(
            str(LazyI18nString(page_content)),
            tags=bleach.ALLOWED_TAGS + ["img", "p", "br", "s", "sup", "sub", "u", "h3", "h4", "h5", "h6"],
            attributes=attributes,
            protocols=bleach.ALLOWED_PROTOCOLS + ["data"],
        )
        gs = GlobalSettingsObject()
        ctx['faq_content'] = False
        if gs.settings.faq_content:
            ctx['faq_content'] = True
        ctx['pricing_content'] = False
        if gs.settings.pricing_content:
            ctx['pricing_content'] = True
        ctx['privacy_content'] = False
        if gs.settings.privacy_content:
            ctx['privacy_content'] = True
        ctx['terms_content'] = False
        if gs.settings.terms_content:
            ctx['terms_content'] = True
        return ctx
