from django.contrib import messages
from django.db import models
from django.http import Http404
from django.utils.translation import ugettext_lazy as _
from django.views.generic import TemplateView

from pretalx.common.views import ActionFromUrl, CreateOrUpdateView
from pretalx.orga.forms import ReviewForm
from pretalx.person.models import EventPermission
from pretalx.submission.models import Review, SubmissionStates


class ReviewContext():

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        submission = self.request.event.submissions.get(code=self.kwargs['code'])
        ctx['submission'] = submission
        ctx['review'] = submission.reviews.filter(user=self.request.user).first()
        return ctx


class ReviewDashboard(TemplateView):

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['my_reviews'] = Review.objects.filter(user=self.request.user, submission__event=self.request.event)
        ctx['missing_reviews'] = Review.find_missing_reviews(self.request.event, self.request.user)
        ctx['pending_submissions'] = self.request.event.submissions.filter(state=SubmissionStates.SUBMITTED).annotate(avg_score=models.Avg('reviews__score')).order_by('-avg_score')
        ctx['reviewers'] = EventPermission.objects.filter(is_reviewer=True, event=self.request.event).count()
        ctx['next_submission'] = Review.find_missing_reviews(self.request.event, self.request.user).first()
        return ctx

    template_name = 'orga/review/dashboard.html'


class ReviewSubmissionList(ReviewContext, TemplateView):
    template_name = 'orga/review/submission_list.html'


class ReviewMySubmission(ReviewContext, ActionFromUrl, CreateOrUpdateView):

    form_class = ReviewForm
    model = Review
    template_name = 'orga/review/submission_create.html'

    @property
    def submission(self):
        return self.request.event.submissions.get(code=self.kwargs['code'])

    def get_object(self):
        return self.submission.reviews.exclude(user__in=self.submission.speakers.all()).filter(user=self.request.user).first()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.submission = self.submission
        form.instance.user = self.request.user
        form.save()
        return super().form_valid(form)

    def get_success_url(self) -> str:

        if self.request.POST.get('show_next', '0').strip() == '1':
            next_submission = Review.find_missing_reviews(self.request.event, self.request.user).first()
            if next_submission:
                messages.success(self.request, _('You are on a roll!'))  # TODO: choose from a list of messages
                return next_submission.orga_urls.new_review
            else:
                messages.success(self.request, _('Nice, you have no submissions left to review!'))
                return self.request.event.orga_urls.reviews

        return self.submission.orga_urls.reviews


class ReviewSubmissionDetail(ReviewContext, CreateOrUpdateView):

    form_class = ReviewForm
    model = Review
    template_name = 'orga/review/submission_detail.html'

    def get_object(self):
        self.submission = self.request.event.submissions.get(code=self.kwargs['code'])
        if 'pk' in self.kwargs:
            return self.submission.reviews.get(pk=self.kwargs['pk'])
        raise Http404()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        kwargs['read_only'] = True
        kwargs['user'] = self.request.user
        return kwargs


class ReviewSubmissionDelete(ReviewContext, TemplateView):
    template_name = 'orga/review/submission_delete.html'
