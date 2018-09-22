import urllib

from csp.decorators import csp_update
from django.contrib import messages
from django.contrib.auth import logout
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.forms.models import BaseModelFormSet, inlineformset_factory
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.views.generic import (
    DetailView, FormView, ListView, TemplateView, UpdateView, View,
)

from pretalx.cfp.forms.submissions import SubmissionInvitationForm
from pretalx.cfp.views.event import LoggedInEventPageMixin
from pretalx.common.phrases import phrases
from pretalx.common.views import is_form_bound
from pretalx.person.forms import LoginInfoForm, SpeakerProfileForm
from pretalx.schedule.forms import AvailabilitiesFormMixin
from pretalx.submission.forms import InfoForm, QuestionsForm, ResourceForm
from pretalx.submission.models import Resource, Submission, SubmissionStates


@method_decorator(csp_update(IMG_SRC="https://www.gravatar.com"), name='dispatch')
class ProfileView(LoggedInEventPageMixin, TemplateView):
    template_name = 'cfp/event/user_profile.html'

    @cached_property
    def login_form(self):
        return LoginInfoForm(
            user=self.request.user,
            data=self.request.POST if is_form_bound(self.request, 'login') else None,
        )

    @cached_property
    def profile_form(self):
        bind = is_form_bound(self.request, 'profile')
        return SpeakerProfileForm(
            user=self.request.user,
            event=self.request.event,
            read_only=False,
            with_email=False,
            data=self.request.POST if bind else None,
            files=self.request.FILES if bind else None,
        )

    @cached_property
    def questions_form(self):
        bind = is_form_bound(self.request, 'questions')
        return QuestionsForm(
            data=self.request.POST if bind else None,
            files=self.request.FILES if bind else None,
            speaker=self.request.user,
            event=self.request.event,
            target='speaker',
            request_user=self.request.user,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['login_form'] = self.login_form
        context['profile_form'] = self.profile_form
        context['questions_form'] = self.questions_form
        context['questions_exist'] = self.request.event.questions.filter(
            target='speaker'
        ).exists()
        return context

    def post(self, request, *args, **kwargs):
        if self.login_form.is_bound and self.login_form.is_valid():
            self.login_form.save()
            request.user.log_action('pretalx.user.password.update')
        elif self.profile_form.is_bound and self.profile_form.is_valid():
            self.profile_form.save()
            profile = self.request.user.profiles.get_or_create(
                event=self.request.event
            )[0]
            profile.log_action('pretalx.user.profile.update', person=request.user)
        elif self.questions_form.is_bound and self.questions_form.is_valid():
            self.questions_form.save()
        else:
            messages.error(self.request, phrases.base.error_saving_changes)
            return super().get(request, *args, **kwargs)

        messages.success(self.request, phrases.base.saved)
        return redirect('cfp:event.user.view', event=self.request.event.slug)


class SubmissionViewMixin:
    permission_required = 'submission.edit_submission'

    def get_object(self):
        users = [self.request.user] if not self.request.user.is_anonymous else []
        return get_object_or_404(
            self.request.event.submissions.prefetch_related(
                'answers', 'answers__options'
            ),
            speakers__in=users,
            code__iexact=self.kwargs.get('code'),
        )


class SubmissionsListView(LoggedInEventPageMixin, ListView):
    template_name = 'cfp/event/user_submissions.html'
    context_object_name = 'submissions'

    def get_context_data(self, **kwargs):
        from pretalx.person.permissions import person_can_view_information

        context = super().get_context_data(**kwargs)
        context['information'] = [
            i
            for i in self.request.event.information.all()
            if person_can_view_information(self.request.user, i)
        ]
        return context

    def get_queryset(self):
        return self.request.event.submissions.filter(speakers__in=[self.request.user])


class SubmissionsWithdrawView(LoggedInEventPageMixin, SubmissionViewMixin, DetailView):
    template_name = 'cfp/event/user_submission_withdraw.html'
    model = Submission
    context_object_name = 'submission'
    permission_required = 'submission.withdraw_submission'

    def get_permission_object(self):
        return self.get_object()

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.state == SubmissionStates.SUBMITTED:
            obj.state = SubmissionStates.WITHDRAWN
            obj.save(update_fields=['state'])
            messages.success(self.request, phrases.cfp.submission_withdrawn)
        else:
            messages.error(self.request, phrases.cfp.submission_not_withdrawn)
        return redirect('cfp:event.user.submissions', event=self.request.event.slug)


class SubmissionConfirmView(LoggedInEventPageMixin, SubmissionViewMixin, FormView):
    permission_required = 'submission.confirm_submission'
    template_name = 'cfp/event/user_submission_confirm.html'
    form_class = AvailabilitiesFormMixin

    def get_object(self):
        return get_object_or_404(
            self.request.event.submissions, code__iexact=self.kwargs.get('code')
        )

    def get_permission_object(self):
        return self.get_object()

    def get_form_kwargs(self):
        result = super().get_form_kwargs()
        result['instance'] = self.request.user.profiles.filter(
            event=self.request.event
        ).first()
        result['event'] = self.request.event
        return result

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['submission'] = self.get_object()
        return context

    def post(self, request, *args, **kwargs):
        submission = self.get_object()
        if submission.state == SubmissionStates.ACCEPTED:
            submission.confirm(person=request.user)
            messages.success(self.request, phrases.cfp.submission_confirmed)
        elif submission.state == SubmissionStates.CONFIRMED:
            messages.success(self.request, phrases.cfp.submission_was_confirmed)
        else:
            messages.error(self.request, phrases.cfp.submission_not_confirmed)
        return redirect('cfp:event.user.submissions', event=self.request.event.slug)


class SubmissionsEditView(LoggedInEventPageMixin, SubmissionViewMixin, UpdateView):
    template_name = 'cfp/event/user_submission_edit.html'
    model = Submission
    form_class = InfoForm
    context_object_name = 'submission'
    permission_required = 'submission.view_submission'
    write_permission_required = 'submission.edit_submission'

    def get_permission_object(self):
        return self.get_object()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['qform'] = self.qform
        context['formset'] = self.formset
        context['can_edit'] = self.can_edit
        return context

    @cached_property
    def formset(self):
        formset_class = inlineformset_factory(
            Submission,
            Resource,
            form=ResourceForm,
            formset=BaseModelFormSet,
            can_delete=True,
            extra=0,
        )
        submission = self.get_object()
        return formset_class(
            self.request.POST if self.request.method == 'POST' else None,
            files=self.request.FILES if self.request.method == 'POST' else None,
            queryset=submission.resources.all()
            if submission
            else Resource.objects.none(),
            prefix='resource',
        )

    def save_formset(self, obj):
        if self.formset.is_valid():
            for form in self.formset.initial_forms:
                if form in self.formset.deleted_forms:
                    if not form.instance.pk:
                        continue
                    obj.log_action(
                        'pretalx.submission.resource.delete',
                        person=self.request.user,
                        data={'id': form.instance.pk},
                    )
                    form.instance.delete()
                    form.instance.pk = None
                elif form.has_changed():
                    form.instance.submission = obj
                    form.save()
                    change_data = {
                        k: form.cleaned_data.get(k) for k in form.changed_data
                    }
                    change_data['id'] = form.instance.pk
                    obj.log_action(
                        'pretalx.submission.resource.update', person=self.request.user
                    )

            for form in self.formset.extra_forms:
                if not form.has_changed():
                    continue
                if self.formset._should_delete_form(form):
                    continue
                form.instance.submission = obj
                form.save()
                obj.log_action(
                    'pretalx.submission.resource.create',
                    person=self.request.user,
                    orga=True,
                    data={'id': form.instance.pk},
                )

            return True
        return False

    @cached_property
    def qform(self):
        return QuestionsForm(
            data=self.request.POST if self.request.method == 'POST' else None,
            files=self.request.FILES if self.request.method == 'POST' else None,
            submission=self.object,
            event=self.request.event,
            readonly=not self.can_edit,
        )

    @cached_property
    def object(self):
        return self.get_object()

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid() and self.qform.is_valid():
            return self.form_valid(form)
        return self.form_invalid(form)

    @cached_property
    def can_edit(self):
        return self.object.editable

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        kwargs['readonly'] = not self.can_edit
        return kwargs

    def form_valid(self, form):
        if self.can_edit:
            form.save()
            self.qform.save()
            result = self.save_formset(form.instance)
            if not result:
                return self.get(self.request, *self.args, **self.kwargs)
            if form.has_changed():
                form.instance.log_action(
                    'pretalx.submission.update', person=self.request.user
                )
            messages.success(self.request, phrases.base.saved)
        else:
            messages.error(self.request, phrases.cfp.submission_uneditable)
        return redirect(self.object.urls.user_base)


class DeleteAccountView(LoggedInEventPageMixin, View):
    @staticmethod
    def post(request, event):

        if request.POST.get('really'):
            request.user.deactivate()
            logout(request)
            messages.success(request, phrases.cfp.account_deleted)
            return redirect(request.event.urls.base)
        messages.error(request, phrases.cfp.account_delete_confirm)
        return redirect(request.event.urls.user + '?really')


class SubmissionInviteView(LoggedInEventPageMixin, SubmissionViewMixin, FormView):
    form_class = SubmissionInvitationForm
    template_name = 'cfp/event/user_submission_invitation.html'
    permission_required = 'submission.edit_submission'

    def get_permission_object(self):
        return self.get_object()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['submission'] = self.get_object()
        kwargs['speaker'] = self.request.user
        if 'email' in self.request.GET and not self.request.method == 'POST':
            initial = kwargs.get('initial', {})
            initial['speaker'] = urllib.parse.unquote(self.request.GET['email'])
            kwargs['initial'] = initial

            try:
                validate_email(initial['speaker'])
            except ValidationError:
                messages.warning(self.request, phrases.cfp.invite_invalid_email)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['submission'] = self.get_object()
        context['invite_url'] = context['submission'].urls.accept_invitation.full()
        return context

    def form_valid(self, form):
        form.save()
        messages.success(self.request, phrases.cfp.invite_sent)
        self.get_object().log_action(
            'pretalx.submission.speakers.invite', person=self.request.user
        )
        return super().form_valid(form)

    def get_success_url(self):
        return self.get_object().urls.user_base


class SubmissionInviteAcceptView(LoggedInEventPageMixin, DetailView):
    template_name = 'cfp/event/invitation.html'
    context_object_name = 'submission'

    def get_object(self, queryset=None):
        return get_object_or_404(
            Submission,
            code__iexact=self.kwargs['code'],
            invitation_token__iexact=self.kwargs['invitation'],
        )

    def post(self, request, *args, **kwargs):
        submission = self.get_object()
        submission.speakers.add(self.request.user)
        submission.log_action(
            'pretalx.submission.speakers.add', person=self.request.user
        )
        submission.save()
        messages.success(self.request, phrases.cfp.invite_accepted)
        return redirect('cfp:event.user.view', event=self.request.event.slug)
