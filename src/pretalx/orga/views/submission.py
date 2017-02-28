from django.contrib import messages
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.utils.translation import ugettext as _
from django.views.generic import CreateView, DetailView, TemplateView, UpdateView, View, ListView

from pretalx.orga.authorization import OrgaPermissionRequired
from pretalx.orga.forms import SubmissionForm
from pretalx.submission.models import Submission, SubmissionStates


class SubmissionAccept(OrgaPermissionRequired, View):
    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        submission = self.request.event.submissions.get(pk=self.kwargs.get('pk'))

        if submission.state not in [SubmissionStates.SUBMITTED, SubmissionStates.REJECTED]:
            messages.error(request, _('A submission must be submitted or rejected to become accepted.'))
            return redirect(reverse('orga:submissions.view', kwargs=self.kwargs))

        submission.state = SubmissionStates.ACCEPTED
        submission.save(update_fields=['state'])
        # TODO: ask for confirmation
        messages.success(request, _('The submission has been accepted.'))
        return redirect(reverse('orga:submissions.view', kwargs=self.kwargs))


class SubmissionReject(OrgaPermissionRequired, View):
    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)

        submission = self.request.event.submissions.get(pk=self.kwargs.get('pk'))
        submission.state = SubmissionStates.REJECTED
        submission.save(update_fields=['state'])
        messages.success(request, _('The submission has been rejected.'))
        return redirect(reverse('orga:submissions.view', kwargs=self.kwargs))


class SubmissionUpdate(OrgaPermissionRequired, UpdateView):
    model = Submission
    form_class = SubmissionForm
    template_name = 'orga/submission/form.html'

    def get_object(self):
        return self.request.event.submissions.get(pk=self.kwargs.get('pk'))

    def get_success_url(self) -> str:
        return reverse('orga:submissions.view', kwargs=self.kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'Yay!')
        form.instance.event = self.request.event
        return super().form_valid(form)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['action'] = 'update'
        return context


class SubmissionDetail(OrgaPermissionRequired, UpdateView):
    model = Submission
    form_class = SubmissionForm
    template_name = 'orga/submission/form.html'

    def get_object(self):
        return self.request.event.submissions.get(pk=self.kwargs.get('pk'))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['read_only'] = True
        return kwargs

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['action'] = 'view'
        return context


class SubmissionList(OrgaPermissionRequired, ListView):
    template_name = 'orga/submission/list.html'
    context_object_name = 'submissions'

    def get_queryset(self):
        return self.request.event.submissions.all()
