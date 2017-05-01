from django.contrib import messages
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.utils.translation import ugettext as _
from django.views.generic import ListView, TemplateView, View

from pretalx.common.views import ActionFromUrl, CreateOrUpdateView
from pretalx.mail.context import template_context_from_submission
from pretalx.orga.authorization import OrgaPermissionRequired
from pretalx.orga.forms import SubmissionForm
from pretalx.person.models import User
from pretalx.submission.models import Submission, SubmissionStates


class SubmissionAccept(OrgaPermissionRequired, View):
    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        submission = self.request.event.submissions.get(pk=self.kwargs.get('pk'))

        if submission.state not in [SubmissionStates.SUBMITTED, SubmissionStates.REJECTED]:
            messages.error(request, _('A submission must be submitted or rejected to become accepted.'))
            return redirect(reverse('orga:submissions.content.view', kwargs=self.kwargs))

        submission.state = SubmissionStates.ACCEPTED
        submission.save(update_fields=['state'])
        submission.log_action('pretalx.submission.accept', person=request.user, orga=True)
        # TODO: ask for confirmation
        messages.success(request, _('The submission has been accepted.'))
        for speaker in submission.speakers.all():
            submission.event.accept_template.to_mail(
                user=speaker, event=self.request.event, context=template_context_from_submission(submission),
                locale=speaker.locale
            )
        return redirect(reverse('orga:submissions.content.view', kwargs=self.kwargs))


class SubmissionReject(OrgaPermissionRequired, View):
    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)

        submission = self.request.event.submissions.get(pk=self.kwargs.get('pk'))
        submission.state = SubmissionStates.REJECTED
        submission.save(update_fields=['state'])
        messages.success(request, _('The submission has been rejected.'))
        submission.log_action('pretalx.submission.reject', person=request.user, orga=True)
        for speaker in submission.speakers.all():
            submission.event.accept_template.to_mail(
                user=speaker, event=self.request.event, context=template_context_from_submission(submission),
                locale=speaker.locale
            )
        return redirect(reverse('orga:submissions.content.view', kwargs=self.kwargs))


class SubmissionSpeakersAdd(OrgaPermissionRequired, View):
    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        submission = self.request.event.submissions.get(pk=self.kwargs.get('pk'))
        speaker = User.objects.get(nick__iexact=request.POST.get('nick'))
        if submission not in speaker.submissions.all():
            speaker.submissions.add(submission)
            speaker.save(update_fields=['submissions'])
            submission.log_action('pretalx.submission.speakers.add', person=request.user, orga=True)
            messages.success(request, _('The speaker has been added to the submission.'))
        else:
            messages.warning(request, _('The speaker was already part of the submission.'))
        return redirect(reverse('orga:submissions.speakers.view', kwargs=self.kwargs))


class SubmissionSpeakersDelete(OrgaPermissionRequired, View):
    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        submission = self.request.event.submissions.get(pk=self.kwargs.get('pk'))
        speaker = User.objects.get(nick__iexact=request.GET.get('nick'))

        if submission in speaker.submissions.all():
            speaker.submissions.remove(submission)
            speaker.save(update_fields=['submissions'])
            submission.log_action('pretalx.submission.speakers.remove', person=request.user, orga=True)
            messages.success(request, _('The speaker has been removed from the submission.'))
        else:
            messages.warning(request, _('The speaker was not part of this submission.'))
        return redirect(reverse('orga:submissions.speakers.view', kwargs=self.kwargs))


class SubmissionSpeakers(OrgaPermissionRequired, TemplateView):
    template_name = 'orga/submission/speakers.html'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['submission'] = self.request.event.submissions.get(pk=self.kwargs.get('pk'))
        context['speakers'] = context['submission'].speakers.all()
        context['users'] = User.objects.all()  # TODO: yeah, no
        return context


class SubmissionQuestions(OrgaPermissionRequired, TemplateView):
    template_name = 'orga/submission/answer_list.html'

    def get_queryset(self):
        submission = self.request.event.submissions.get(pk=self.kwargs.get('pk'))
        return submission.answers.all()

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        submission = self.request.event.submissions.get(pk=self.kwargs.get('pk'))
        user_list = [{
            'speaker': user,
            'answers': submission.answers.all()  # TODO: filter
        } for user in submission.speakers.all()]
        context.update({
            'user_list': user_list,
            'submission': submission,
        })
        return context


class SubmissionContent(OrgaPermissionRequired, ActionFromUrl, CreateOrUpdateView):
    model = Submission
    form_class = SubmissionForm
    template_name = 'orga/submission/content.html'

    def get_object(self):
        return self.request.event.submissions.get(pk=self.kwargs.get('pk'))

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['submission'] = self.request.event.submissions.get(pk=self.kwargs.get('pk'))
        return context

    def get_success_url(self) -> str:
        return reverse('orga:submissions.content.view', kwargs=self.kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'The submission has been updated!')
        if form.has_changed():
            action = 'pretalx.submission.' + ('update' if self.object else 'create')
            form.instance.log_action(action, person=self.request.user, orga=True)
        form.instance.event = self.request.event
        return super().form_valid(form)


class SubmissionList(OrgaPermissionRequired, ListView):
    template_name = 'orga/submission/list.html'
    context_object_name = 'submissions'

    def get_queryset(self):
        return self.request.event.submissions.all()
