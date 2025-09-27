import sys

from django.conf import settings
from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, FormView, ListView, TemplateView
from django_context_decorator import context
from django_scopes import scopes_disabled

from eventyay.celery_app import app
from eventyay.common.image import gravatar_csp
from eventyay.base.models.settings import GlobalSettings
from eventyay.common.text.phrases import phrases
from eventyay.base.services.update_check import check_result_table, update_check
from eventyay.common.views.mixins import ActionConfirmMixin, PermissionRequired
from eventyay.orga.forms.admin import UpdateSettingsForm
from eventyay.base.models import User


class AdminDashboard(PermissionRequired, TemplateView):
    template_name = 'orga/admin/admin.html'
    permission_required = 'person.administrator_user'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        site_name = dict(settings.TALK_CONFIG.items('site')).get('name')
        context['site_name'] = site_name
        context['base_path'] = settings.BASE_PATH
        context['settings'] = settings
        return context

    @context
    def queue_length(self):
        if settings.CELERY_TASK_ALWAYS_EAGER:
            return None
        try:
            client = app.broker_connection().channel().client
            return client.llen('celery')
        except Exception as e:
            return str(e)

    @context
    def executable(self):
        return sys.executable

    @context
    def eventyay_version(self):
        return settings.EVENTYAY_VERSION


class UpdateCheckView(PermissionRequired, FormView):
    template_name = 'orga/admin/update.html'
    permission_required = 'person.administrator_user'
    form_class = UpdateSettingsForm

    def post(self, request, *args, **kwargs):
        if 'trigger' in request.POST:
            update_check.apply()
            return redirect(self.get_success_url())
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        form.save()
        messages.success(self.request, phrases.base.saved)
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, phrases.base.error_saving_changes)
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        result['gs'] = GlobalSettings()
        result['gs'].settings.set('update_check_ack', True)
        return result

    @context
    def result_table(self):
        return check_result_table()

    def get_success_url(self):
        return reverse('orga:admin.update')


class AdminUserList(PermissionRequired, ListView):
    template_name = 'orga/admin/user_list.html'
    permission_required = 'person.administrator_user'
    model = User
    context_object_name = 'users'
    paginate_by = '250'

    def dispatch(self, *args, **kwargs):
        with scopes_disabled():
            return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        search = self.request.GET.get('q', '').strip()
        if not search or len(search) < 3:
            return User.objects.none()
        return (
            User.objects.filter(Q(fullname__icontains=search) | Q(email__icontains=search))
            .prefetch_related(
                'teams',
                'teams__organizer',
                'teams__organizer__events',
                'teams__limit_events',
            )
            .annotate(
                submission_count=Count('submissions', distinct=True),
            )
        )

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action') or '-'
        action, user_id = action.split('-')
        user = User.objects.get(pk=user_id)
        if action == 'reset':
            user.reset_password(event=None)
            messages.success(request, phrases.base.password_reset_success)
        return super().get(request, *args, **kwargs)


class AdminUserDetail(PermissionRequired, DetailView):
    template_name = 'orga/admin/user_detail.html'
    permission_required = 'person.administrator_user'
    model = User
    context_object_name = 'user'
    slug_url_kwarg = 'code'
    slug_field = 'code'

    @gravatar_csp()
    def dispatch(self, *args, **kwargs):
        with scopes_disabled():
            return super().dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action') or '-'
        if action == 'pw-reset':
            self.get_object().reset_password(event=None)
            messages.success(request, phrases.base.password_reset_success)
        elif action == 'deactivate':
            user = self.get_object()
            user.is_active = False
            user.save()
            messages.success(request, _('The user has been deactivated.'))
        elif action == 'activate':
            user = self.get_object()
            user.is_active = True
            user.save()
            messages.success(request, _('The user has been activated.'))
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse('orga:admin.user.list')

    @context
    def tablist(self):
        return {
            'teams': _('Teams'),
            'submissions': _('Proposals'),
            'actions': _('Last actions'),
        }

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        result['teams'] = self.object.teams.all().prefetch_related('organizer', 'limit_events', 'organizer__events')
        result['submissions'] = self.object.submissions.all()
        result['last_actions'] = self.object.own_actions()[:10]
        return result


class AdminUserDelete(ActionConfirmMixin, AdminUserDetail):
    @property
    def action_object_name(self):
        return _('User') + f': {self.get_object().fullname if self.get_object().fullname else self.get_object().email}'

    @property
    def action_next_url(self):
        return self.get_success_url()

    @property
    def action_back_url(self):
        return reverse('orga:admin.user.view', kwargs={'code': self.get_object().code})

    def dispatch(self, *args, **kwargs):
        with scopes_disabled():
            return super().dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.get_object().shred()
        messages.success(request, _('The user has been deleted.'))
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse('orga:admin.user.list')
