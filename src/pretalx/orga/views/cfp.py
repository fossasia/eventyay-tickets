from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.views.generic import CreateView, DetailView, TemplateView, UpdateView, View, ListView

from pretalx.orga.authorization import OrgaPermissionRequired
from pretalx.orga.forms import CfPForm, QuestionForm, SubmissionTypeForm
from pretalx.person.models import User
from pretalx.submission.models import CfP, Question, SubmissionType


class CfPTextDetail(OrgaPermissionRequired, UpdateView):
    form_class = CfPForm
    model = CfP
    slug_url_kwarg = 'event'
    slug_field = 'slug'
    template_name = 'orga/cfp/text.html'

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


class CfPTextUpdate(OrgaPermissionRequired, UpdateView):
    model = CfP
    slug_url_kwarg = 'event'
    slug_field = 'slug'
    form_class = CfPForm
    template_name = 'orga/cfp/text.html'

    def get_object(self):
        return self.request.event.get_cfp()

    def get_success_url(self) -> str:
        return reverse('orga:cfp.text.view', kwargs={'event': self.object.event.slug})

    def form_valid(self, form):
        messages.success(self.request, 'Yay!')
        form.instance.event = self.request.event
        ret = super().form_valid(form)
        return ret

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['action'] = 'update'
        return context


class CfPQuestionList(OrgaPermissionRequired, ListView):
    template_name = 'orga/cfp/question_view.html'
    context_object_name = 'questions'

    def get_queryset(self):
        return self.request.event.questions.all()


class CfPQuestionCreate(OrgaPermissionRequired, CreateView):
    model = Question
    slug_url_kwarg = 'event'
    slug_field = 'slug'
    form_class = QuestionForm
    template_name = 'orga/cfp/question_form.html'

    def get_success_url(self) -> str:
        return reverse('orga:cfp.questions.view', kwargs={'event': self.object.event.slug})

    def form_valid(self, form):
        messages.success(self.request, 'Yay!')
        form.instance.event = self.request.event
        ret = super().form_valid(form)
        return ret

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['action'] = 'create'
        return context


class CfPQuestionDetail(OrgaPermissionRequired, UpdateView):
    model = CfP
    slug_url_kwarg = 'event'
    slug_field = 'slug'
    form_class = QuestionForm
    template_name = 'orga/cfp/question_form.html'

    def get_object(self):
        return self.request.event.questions.get(pk=self.kwargs.get('pk'))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['read_only'] = True
        return kwargs

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['action'] = 'view'
        return context


class CfPQuestionUpdate(OrgaPermissionRequired, UpdateView):
    model = CfP
    slug_url_kwarg = 'event'
    slug_field = 'slug'
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

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['action'] = 'update'
        return context


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


class SubmissionTypeCreate(OrgaPermissionRequired, CreateView):
    model = SubmissionType
    form_class = SubmissionTypeForm
    template_name = 'orga/cfp/submission_type_form.html'

    def get_success_url(self) -> str:
        return reverse('orga:cfp.types.view', kwargs={'event': self.object.event.slug})

    def form_valid(self, form):
        messages.success(self.request, 'Yay!')
        form.instance.event = self.request.event
        ret = super().form_valid(form)
        return ret

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['action'] = 'create'
        return context


class SubmissionTypeDefault(OrgaPermissionRequired, View):

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)

        submission_type = self.request.event.submission_types.get(pk=self.kwargs.get('pk'))
        self.request.event.cfp.default_type = submission_type
        self.request.event.cfp.save(update_fields=['default_type'])
        messages.success(request, _('The SubmissionType has been made default.'))
        return redirect(reverse('orga:cfp.types.view', kwargs={'event': self.request.event.slug}))


class SubmissionTypeUpdate(OrgaPermissionRequired, UpdateView):
    model = SubmissionType
    form_class = SubmissionTypeForm
    template_name = 'orga/cfp/submission_type_form.html'

    def get_object(self):
        return self.request.event.submission_types.get(pk=self.kwargs.get('pk'))

    def get_success_url(self) -> str:
        return reverse('orga:cfp.types.view', kwargs={'event': self.object.event.slug})

    def form_valid(self, form):
        messages.success(self.request, 'Yay!')
        form.instance.event = self.request.event
        ret = super().form_valid(form)
        return ret

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['action'] = 'update'
        return context


class SubmissionTypeDelete(OrgaPermissionRequired, View):

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)

        submission_type = self.request.event.submission_types.get(pk=self.kwargs.get('pk'))
        submission_type.delete()
        messages.success(request, _('The Submission Type has been deleted.'))
        return redirect(reverse('orga:cfp.types.view', kwargs={'event': self.request.event.slug}))
