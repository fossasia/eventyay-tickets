import json
from collections import OrderedDict
from datetime import timedelta
from io import BytesIO

from django.contrib import messages
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.templatetags.static import static
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView
from reportlab.lib import pagesizes
from reportlab.pdfgen import canvas

from eventyay.base.models import CachedFile, OrderPosition, Question, QuestionAnswer
from eventyay.base.services.tickets import invalidate_cache
from eventyay.base.views.cachedfiles import DownloadView
from eventyay.base.views.tasks import AsyncAction
from eventyay.control.permissions import EventPermissionRequiredMixin
from eventyay.control.views.pdf import BaseEditorView, open_stored_pdf_file
from eventyay.helpers.models import modelcopy
from eventyay.plugins.badges.forms import BadgeLayoutForm, BadgeLayoutSettingsForm, BadgeSettingsForm
from eventyay.plugins.badges.tasks import badges_create_pdf
from eventyay.plugins.badges.utils import (
    BADGE_TICKET_PROVIDER,
    clear_badge_layout_cache,
    delete_badge_cached_pdfs,
    get_event_allowed_badge_placeholders,
)

from .exporters import BadgeRenderer, _open_layout_background
from .models import BadgeLayout


class LayoutGetDefault(EventPermissionRequiredMixin, View):
    permission = 'can_change_event_settings'

    def get(self, request, *args, **kwargs):
        layout = BadgeLayout.objects.get_or_create(
            event=request.event,
            default=True,
            defaults={'name': _('Default layout')},
        )[0]
        return redirect(
            reverse(
                'plugins:badges:edit',
                kwargs={
                    'organizer': request.event.organizer.slug,
                    'event': request.event.slug,
                    'layout': layout.pk,
                },
            )
        )


class BadgePluginEnabledMixin:
    def dispatch(self, request, *args, **kwargs):
        if 'eventyay.plugins.badges' not in request.event.get_plugins():
            return redirect(
                'eventyay_common:event.plugins',
                organizer=request.event.organizer.slug,
                event=request.event.slug,
            )
        return super().dispatch(request, *args, **kwargs)


def _schedule_badge_cache_invalidation(event):
    event_pk = event.pk
    clear_badge_layout_cache(event)
    delete_badge_cached_pdfs(event)
    transaction.on_commit(
        lambda event_pk=event_pk: invalidate_cache.apply_async(
            kwargs={'event': event_pk, 'provider': BADGE_TICKET_PROVIDER}
        )
    )


class LayoutListView(BadgePluginEnabledMixin, EventPermissionRequiredMixin, ListView):
    model = BadgeLayout
    permission = ('can_change_event_settings', 'can_view_orders')
    template_name = 'pretixplugins/badges/index.html'
    context_object_name = 'layouts'

    def get_queryset(self):
        return self.request.event.badge_layouts.prefetch_related('product_assignments')


class LayoutSettingsView(BadgePluginEnabledMixin, EventPermissionRequiredMixin, FormView):
    form_class = BadgeLayoutSettingsForm
    template_name = 'pretixplugins/badges/settings.html'
    permission = 'can_change_event_settings'

    @cached_property
    def layout(self):
        try:
            return self.request.event.badge_layouts.get(id=self.kwargs['layout'])
        except BadgeLayout.DoesNotExist:
            raise Http404(_('The requested badge layout does not exist.'))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(
            {
                'event': self.request.event,
                'layout': self.layout,
            }
        )
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['layout'] = self.layout
        return ctx

    @transaction.atomic
    def form_valid(self, form):
        form.save()
        _schedule_badge_cache_invalidation(self.request.event)
        self.layout.log_action(
            action='eventyay.plugins.badges.layout.changed',
            user=self.request.user,
            data={
                'products': list(form.cleaned_data['products'].values_list('pk', flat=True)),
                'vouchers': list(form.cleaned_data['vouchers'].values_list('pk', flat=True)),
                'allow_customization': form.cleaned_data['allow_customization'],
                'allow_badge_editing': form.cleaned_data['allow_badge_editing'],
                'ask_user_fields': form.cleaned_data['ask_user_fields'],
                'required_badge_fields': form.cleaned_data['required_badge_fields'],
            },
        )
        messages.success(self.request, _('Your badge layout settings have been saved.'))
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, _('We could not save your changes. See below for details.'))
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse(
            'plugins:badges:settings',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
                'layout': self.layout.pk,
            },
        )


class BadgeSettingsView(BadgePluginEnabledMixin, EventPermissionRequiredMixin, FormView):
    form_class = BadgeSettingsForm
    template_name = 'pretixplugins/badges/event_settings.html'
    permission = 'can_change_event_settings'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        return kwargs

    def form_valid(self, form):
        allowed = form.save()
        _schedule_badge_cache_invalidation(self.request.event)
        self.request.event.log_action(
            action='eventyay.plugins.badges.settings.changed',
            user=self.request.user,
            data={'badge_allowed_placeholders': allowed},
        )
        messages.success(self.request, _('Your badge settings have been saved.'))
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, _('We could not save your changes. See below for details.'))
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse(
            'plugins:badges:event_settings',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )


EventBadgeSettingsView = BadgeSettingsView


class LayoutCreate(BadgePluginEnabledMixin, EventPermissionRequiredMixin, CreateView):
    model = BadgeLayout
    form_class = BadgeLayoutForm
    template_name = 'pretixplugins/badges/edit.html'
    permission = 'can_change_event_settings'
    context_object_name = 'layout'
    success_url = '/ignored'

    @transaction.atomic
    def form_valid(self, form):
        form.instance.event = self.request.event
        if not self.request.event.badge_layouts.filter(default=True).exists():
            form.instance.default = True
        messages.success(self.request, _('The new badge layout has been created.'))
        super().form_valid(form)
        if form.instance.background and form.instance.background.name:
            form.instance.background.save('background.pdf', form.instance.background)
        _schedule_badge_cache_invalidation(self.request.event)
        form.instance.log_action(
            'eventyay.plugins.badges.layout.added',
            user=self.request.user,
            data=dict(form.cleaned_data),
        )
        return redirect(
            reverse(
                'plugins:badges:edit',
                kwargs={
                    'organizer': self.request.event.organizer.slug,
                    'event': self.request.event.slug,
                    'layout': form.instance.pk,
                },
            )
        )

    def form_invalid(self, form):
        messages.error(self.request, _('We could not save your changes. See below for details.'))
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs)

    @cached_property
    def copy_from(self):
        if self.request.GET.get('copy_from') and not getattr(self, 'object', None):
            try:
                return self.request.event.badge_layouts.get(pk=self.request.GET.get('copy_from'))
            except BadgeLayout.DoesNotExist:
                pass

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()

        if self.copy_from:
            i = modelcopy(self.copy_from)
            i.pk = None
            i.default = False
            kwargs['instance'] = i
            kwargs.setdefault('initial', {})
        return kwargs


class LayoutSetDefault(BadgePluginEnabledMixin, EventPermissionRequiredMixin, DetailView):
    model = BadgeLayout
    permission = 'can_change_event_settings'

    def get_object(self, queryset=None) -> BadgeLayout:
        try:
            return self.request.event.badge_layouts.get(id=self.kwargs['layout'])
        except BadgeLayout.DoesNotExist:
            raise Http404(_('The requested badge layout does not exist.'))

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        messages.success(self.request, _('Your changes have been saved.'))
        obj = self.get_object()
        self.request.event.badge_layouts.exclude(pk=obj.pk).update(default=False)
        obj.default = True
        obj.save(update_fields=['default'])
        _schedule_badge_cache_invalidation(self.request.event)
        return redirect(self.get_success_url())

    def get_success_url(self) -> str:
        return reverse(
            'plugins:badges:index',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )


class LayoutDelete(BadgePluginEnabledMixin, EventPermissionRequiredMixin, DeleteView):
    model = BadgeLayout
    template_name = 'pretixplugins/badges/delete.html'
    permission = 'can_change_event_settings'
    context_object_name = 'layout'

    def get_object(self, queryset=None) -> BadgeLayout:
        try:
            return self.request.event.badge_layouts.get(id=self.kwargs['layout'])
        except BadgeLayout.DoesNotExist:
            raise Http404(_('The requested badge layout does not exist.'))

    @transaction.atomic
    def form_valid(self, form):
        self.object = self.get_object()
        self.object.log_action(action='eventyay.plugins.badges.layout.deleted', user=self.request.user)
        self.object.delete()
        if not self.request.event.badge_layouts.filter(default=True).exists():
            f = self.request.event.badge_layouts.first()
            if f:
                f.default = True
                f.save(update_fields=['default'])
        _schedule_badge_cache_invalidation(self.request.event)
        messages.success(self.request, _('The selected badge layout been deleted.'))
        return redirect(self.get_success_url())

    def get_success_url(self) -> str:
        return reverse(
            'plugins:badges:index',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )


class LayoutEditorView(BaseEditorView):
    @cached_property
    def layout(self):
        try:
            return self.request.event.badge_layouts.get(id=self.kwargs['layout'])
        except BadgeLayout.DoesNotExist:
            raise Http404(_('The requested badge layout does not exist.'))

    @property
    def title(self):
        return _('Badge layout: {}').format(self.layout)

    def get_variables(self):
        all_variables = super().get_variables()
        allowed_keys = set(get_event_allowed_badge_placeholders(self.request.event))
        filtered = OrderedDict()
        for k, v in all_variables.items():
            canonical = v.get('canonical_key', k)
            if k in allowed_keys or canonical in allowed_keys:
                filtered[k] = v
        return filtered

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['allowed_keys'] = get_event_allowed_badge_placeholders(self.request.event)
        return ctx

    def _get_preview_position(self):
        p = super()._get_preview_position()
        p.job_title = _('Sample job title')
        p.company = _('Sample company')
        p.save(update_fields=['job_title', 'company'])

        sample_answers = {
            Question.TYPE_BOOLEAN: 'True',
            Question.TYPE_NUMBER: '42',
            Question.TYPE_DATE: '2026-01-01',
            Question.TYPE_TIME: '12:00',
            Question.TYPE_DATETIME: '2026-01-01T12:00:00+00:00',
            Question.TYPE_COUNTRYCODE: 'US',
            Question.TYPE_PHONENUMBER: '+1 202 555 0123',
        }

        questions = self.request.event.questions.exclude(type=Question.TYPE_FILE).prefetch_related('options')
        for question in questions:
            answer_text = sample_answers.get(question.type, str(question.question))
            answer = QuestionAnswer.objects.get_or_create(
                orderposition=p,
                question=question,
                defaults={'answer': answer_text},
            )[0]

            if question.type in Question.OPTION_TYPES:
                option = question.options.first()
                if option:
                    answer.answer = option.answer
                    answer.save(update_fields=['answer'])
                    answer.options.set([option])
                else:
                    answer.answer = ''
                    answer.save(update_fields=['answer'])
            elif answer.answer != answer_text:
                answer.answer = answer_text
                answer.save(update_fields=['answer'])

        return p

    def save_layout(self, layout_data=None):
        if layout_data is None:
            layout_data = self._get_posted_layout_json()
        if layout_data is None:
            layout_data = '[]'
        self.layout.layout = layout_data
        self.layout.save(update_fields=['layout'])
        _schedule_badge_cache_invalidation(self.request.event)
        self.layout.log_action(
            action='eventyay.plugins.badges.layout.changed',
            user=self.request.user,
            data={'layout': layout_data},
        )

    def get_default_background(self):
        return static('pretixplugins/badges/badge_default_a6l.pdf')

    def generate(self, op: OrderPosition, override_layout=None, override_background=None):
        BadgeRenderer._register_fonts()

        buffer = BytesIO()
        if override_background:
            bgf = default_storage.open(override_background.name, 'rb')
        else:
            bgf = _open_layout_background(self.layout)
        r = BadgeRenderer(
            self.request.event,
            override_layout or self.get_current_layout(),
            bgf,
            ask_user_fields=(self.layout.ask_user_fields_data if self.layout.allow_customization else []),
            required_fields=self.layout.required_badge_fields_data,
        )
        p = canvas.Canvas(buffer, pagesize=pagesizes.A4)
        r.draw_page(p, op.order, op)
        p.save()
        outbuffer = r.render_background(buffer, 'Badge')
        return 'badge.pdf', 'application/pdf', outbuffer.read()

    def get_current_layout(self):
        return self._normalize_layout(json.loads(self.layout.layout))

    def get_current_background(self):
        return self.layout.background.url if self.layout.background else self.get_default_background()

    def _open_saved_background_pdf(self):
        return open_stored_pdf_file(
            self.layout.background,
            default_path='pretixplugins/badges/badge_default_a6l.pdf',
        )

    def save_background(self, f: CachedFile):
        # The editor creates a blank placeholder PDF for on-canvas sizing. Do not
        # replace the layout artwork when the user only saves field positions.
        if not f.file:
            return
        if f.file.name.endswith('empty.pdf'):
            return
        try:
            if f.file.size < 15_000:
                with f.file.open('rb') as handle:
                    if b'ReportLab Generated PDF' in handle.read(120):
                        return
        except OSError:
            pass
        if self.layout.background:
            self.layout.background.delete()
        self.layout.background.save('background.pdf', f.file)
        _schedule_badge_cache_invalidation(self.request.event)


class OrderPrintDo(BadgePluginEnabledMixin, EventPermissionRequiredMixin, AsyncAction, View):
    task = badges_create_pdf
    permission = 'can_view_orders'
    known_errortypes = ['OrderError']

    def get_success_message(self, value):
        return None

    def get_success_url(self, value):
        url = reverse('plugins:badges:download', kwargs={
            'organizer': self.request.event.organizer.slug,
            'event': self.request.event.slug,
            'id': str(value)
        })
        if self.request.GET.get('action') != 'download':
            url += '?inline=1'
        return url

    def get_error_url(self):
        return reverse(
            'control:event.index',
            kwargs={
                'organizer': self.request.organizer.slug,
                'event': self.request.event.slug,
            },
        )

    def get_error_message(self, exception):
        if isinstance(exception, str):
            return exception
        return super().get_error_message(exception)

    def post(self, request, *args, **kwargs):
        order = get_object_or_404(self.request.event.orders, code=request.GET.get('code'))
        cf = CachedFile(web_download=True, session_key=self.request.session.session_key)
        cf.date = now()
        cf.type = 'application/pdf'
        cf.expires = now() + timedelta(days=3)
        if 'position' in request.GET:
            qs = order.positions.filter(pk=request.GET.get('position'))
            positions = [p.pk for p in qs]
            if len(positions) < 5:
                cf.filename = (
                    f'badges_{self.request.event.slug}_{order.code}_{"_".join(str(p.positionid) for p in qs)}.pdf'
                )
        else:
            positions = [p.pk for p in order.positions.all()]
            cf.filename = f'badges_{self.request.event.slug}_{order.code}.pdf'
        cf.save()
        return self.do(
            self.request.event.pk,
            str(cf.id),
            positions,
        )


class BadgeCachedDownloadView(DownloadView):
    @method_decorator(xframe_options_sameorigin)
    def get(self, request, *args, **kwargs):
        resp = super().get(request, *args, **kwargs)
        if request.GET.get('inline') in ('1', 'true') and getattr(self.object, 'file', None):
            resp['Content-Disposition'] = f'inline; filename="{self.object.filename}"'
        return resp
