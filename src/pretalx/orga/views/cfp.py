from django.contrib import messages
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.views.generic import ListView, UpdateView, View

from pretalx.common.views import ActionFromUrl, CreateOrUpdateView
from pretalx.orga.authorization import OrgaPermissionRequired
from pretalx.orga.forms import CfPForm, QuestionForm, SubmissionTypeForm
from pretalx.orga.forms.cfp import CfPSettingsForm
from pretalx.submission.models import CfP, Question, SubmissionType


class CfPTextDetail(OrgaPermissionRequired, ActionFromUrl, UpdateView):
    form_class = CfPForm
    model = CfP
    template_name = 'orga/cfp/text.html'

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['sform'] = self.sform
        return ctx

    @cached_property
    def sform(self):
        return CfPSettingsForm(
            read_only=(self._action == 'view'),
            locales=self.request.event.locales,
            obj=self.request.event,
            attribute_name='settings',
            data=self.request.POST if self.request.method == "POST" else None,
            prefix='settings'
        )

    def get_object(self):
        return self.request.event.get_cfp()

    def get_success_url(self) -> str:
        return reverse('orga:cfp.text.view', kwargs={'event': self.object.event.slug})

    def form_valid(self, form):
        if not self.sform.is_valid():
            return self.form_invalid(form)
        messages.success(self.request, 'Yay!')
        form.instance.event = self.request.event
        ret = super().form_valid(form)
        self.sform.save()
        return ret


class CfPQuestionList(OrgaPermissionRequired, ListView):
    template_name = 'orga/cfp/question_view.html'
    context_object_name = 'questions'

    def get_queryset(self):
        return self.request.event.questions.all()


class CfPQuestionDetail(OrgaPermissionRequired, ActionFromUrl, CreateOrUpdateView):
    model = Question
    form_class = QuestionForm
    template_name = 'orga/cfp/question_form.html'

    def get_object(self):
        return self.request.event.questions.get(pk=self.kwargs.get('pk'))

    def get_success_url(self) -> str:
        return reverse('orga:cfp.questions.view', kwargs={'event': self.object.event.slug})

    def form_valid(self, form):
        messages.success(self.request, 'Yay!')
        form.instance.event = self.request.event
        ret = super().form_valid(form)
        return ret


class CfPQuestionDelete(OrgaPermissionRequired, View):

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)

        question = self.request.event.questions.get(pk=self.kwargs.get('pk'))
        question.delete()
        messages.success(request, _('The Question has been deleted.'))
        return redirect(reverse('orga:cfp.questions.view', kwargs={'event': self.request.event}))


class SubmissionTypeList(OrgaPermissionRequired, ListView):
    template_name = 'orga/cfp/submission_type_view.html'
    context_object_name = 'types'

    def get_queryset(self):
        return self.request.event.submission_types.all()


class SubmissionTypeDetail(OrgaPermissionRequired, ActionFromUrl, CreateOrUpdateView):
    model = SubmissionType
    form_class = SubmissionTypeForm
    template_name = 'orga/cfp/submission_type_form.html'

    def get_success_url(self) -> str:
        return reverse('orga:cfp.types.view', kwargs={'event': self.object.event.slug})

    def get_object(self):
        return self.request.event.submission_types.get(pk=self.kwargs.get('pk'))

    def form_valid(self, form):
        messages.success(self.request, 'Yay!')
        form.instance.event = self.request.event
        ret = super().form_valid(form)
        return ret


class SubmissionTypeDefault(OrgaPermissionRequired, View):

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)

        submission_type = self.request.event.submission_types.get(pk=self.kwargs.get('pk'))
        self.request.event.cfp.default_type = submission_type
        self.request.event.cfp.save(update_fields=['default_type'])
        messages.success(request, _('The SubmissionType has been made default.'))
        return redirect(reverse('orga:cfp.types.view', kwargs={'event': self.request.event.slug}))


class SubmissionTypeDelete(OrgaPermissionRequired, View):

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)

        submission_type = self.request.event.submission_types.get(pk=self.kwargs.get('pk'))
        submission_type.delete()
        messages.success(request, _('The Submission Type has been deleted.'))
        return redirect(reverse('orga:cfp.types.view', kwargs={'event': self.request.event.slug}))
