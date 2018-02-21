from django.contrib import messages
from django.db import models
from django.shortcuts import get_object_or_404, redirect
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.views.generic import ListView, TemplateView

from pretalx.common.mixins.views import PermissionRequired
from pretalx.common.phrases import phrases
from pretalx.common.views import CreateOrUpdateView
from pretalx.orga.forms import ReviewForm
from pretalx.person.models import EventPermission
from pretalx.submission.forms import QuestionsForm
from pretalx.submission.models import Review, SubmissionStates


class ReviewDashboard(PermissionRequired, ListView):
    template_name = 'orga/review/dashboard.html'
    paginate_by = 25
    context_object_name = 'submissions'
    permission_required = 'orga.view_review_dashboard'

    def get_queryset(self, *args, **kwargs):
        overridden_reviews = Review.objects.filter(override_vote__isnull=False, submission_id=models.OuterRef('pk'))
        return self.request.event.submissions\
            .filter(state__in=[SubmissionStates.SUBMITTED, SubmissionStates.ACCEPTED, SubmissionStates.REJECTED, SubmissionStates.CONFIRMED])\
            .order_by('review_id')\
            .annotate(has_override=models.Exists(overridden_reviews))\
            .annotate(avg_score=models.Case(
                models.When(
                    has_override=True,
                    then=self.request.event.settings.review_max_score + 1,
                ),
                default=models.Avg('reviews__score')
            ))\
            .order_by('-state', '-avg_score', 'code')

    def get_permission_object(self):
        return self.request.event

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        missing_reviews = Review.find_missing_reviews(self.request.event, self.request.user)
        reviewers = EventPermission.objects.filter(is_reviewer=True, event=self.request.event)
        ctx['missing_reviews'] = missing_reviews
        ctx['next_submission'] = missing_reviews.first()
        ctx['reviewers'] = reviewers.count()
        ctx['active_reviewers'] = reviewers.filter(user__reviews__isnull=False).order_by('user__id').distinct().count()
        ctx['review_count'] = self.request.event.reviews.count()
        if ctx['active_reviewers'] > 1:
            ctx['avg_reviews'] = round(ctx['review_count'] / ctx['active_reviewers'], 1)
        return ctx


class ReviewSubmission(PermissionRequired, CreateOrUpdateView):

    form_class = ReviewForm
    model = Review
    template_name = 'orga/submission/review.html'
    permission_required = 'submission.view_reviews'

    @cached_property
    def submission(self):
        return get_object_or_404(
            self.request.event.submissions,
            code__iexact=self.kwargs['code'],
        )

    @cached_property
    def object(self):
        return self.submission.reviews.exclude(user__in=self.submission.speakers.all()).filter(user=self.request.user).first()

    def get_object(self):
        return self.object

    def get_permission_object(self):
        return self.submission

    @cached_property
    def read_only(self):
        return not self.request.user.has_perm('submission.review_submission', self.get_object() or self.submission)

    @cached_property
    def qform(self):
        return QuestionsForm(
            target='reviewer', event=self.request.event,
            data=(self.request.POST if self.request.method == 'POST' else None),
            files=(self.request.FILES if self.request.method == 'POST' else None),
            speaker=self.request.user,
            review=self.object,
            readonly=self.read_only,
        )

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['submission'] = self.submission
        ctx['review'] = self.object
        ctx['read_only'] = self.read_only
        ctx['override_left'] = self.request.user.remaining_override_votes(self.request.event)
        ctx['qform'] = self.qform
        ctx['reviews'] = [{
                'score': review.display_score,
                'text': review.text,
                'user': review.user.get_display_name(),
                'answers': [
                    review.answers.filter(question=question).first()
                    for question in self.qform.queryset
                ]
            } for review in self.submission.reviews.exclude(pk=(self.object.pk if self.object else None))
        ]
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        kwargs['user'] = self.request.user
        kwargs['read_only'] = self.read_only
        return kwargs

    def form_valid(self, form):
        if not self.qform.is_valid():
            messages.error(self.request, _('There have been erros with your input.'))
            return redirect(self.get_success_url())
        form.instance.submission = self.submission
        form.instance.user = self.request.user
        if not form.instance.pk:
            if not self.request.user.has_perm('submission.review_submission', self.submission):
                messages.error(self.request, _('You cannot review this submission at this time.'))
                return redirect(self.get_success_url())
        if form.instance.pk and not self.request.user.has_perm('submission.edit_review', form.instance):
            messages.error(self.request, _('You cannot review this submission at this time.'))
            return redirect(self.get_success_url())
        form.save()
        self.qform.review = form.instance
        self.qform.save()
        return super().form_valid(form)

    def get_success_url(self) -> str:
        if self.request.POST.get('show_next', '0').strip() == '1':
            next_submission = Review.find_missing_reviews(self.request.event, self.request.user).first()
            if next_submission:
                messages.success(self.request, phrases.orga.another_review)
                return next_submission.orga_urls.reviews
            else:
                messages.success(self.request, _('Nice, you have no submissions left to review!'))
                return self.request.event.orga_urls.reviews

        return self.submission.orga_urls.reviews


class ReviewSubmissionDelete(PermissionRequired, TemplateView):
    template_name = 'orga/review/submission_delete.html'
    permission_required = 'orga.remove_review'

    def get_permission_object(self):
        return self.request.event
