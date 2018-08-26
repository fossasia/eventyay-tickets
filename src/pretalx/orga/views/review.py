from django.contrib import messages
from django.db import models
from django.shortcuts import get_object_or_404, redirect
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.views.generic import ListView, TemplateView

from pretalx.common.mixins.views import Filterable, PermissionRequired
from pretalx.common.phrases import phrases
from pretalx.common.views import CreateOrUpdateView
from pretalx.orga.forms import ReviewForm
from pretalx.person.models import User
from pretalx.submission.forms import QuestionsForm, SubmissionFilterForm
from pretalx.submission.models import Review, SubmissionStates


class ReviewDashboard(PermissionRequired, Filterable, ListView):
    template_name = 'orga/review/dashboard.html'
    paginate_by = 25
    context_object_name = 'submissions'
    permission_required = 'orga.view_review_dashboard'
    default_filters = (
        'code__icontains',
        'speakers__name__icontains',
        'title__icontains',
    )
    filter_fields = ('submission_type', 'state')

    def get_filter_form(self):
        return SubmissionFilterForm(
            data=self.request.GET,
            event=self.request.event,
            usable_states=[
                SubmissionStates.SUBMITTED,
                SubmissionStates.ACCEPTED,
                SubmissionStates.REJECTED,
                SubmissionStates.CONFIRMED,
            ],
        )

    def get_queryset(self, *args, **kwargs):
        overridden_reviews = Review.objects.filter(
            override_vote__isnull=False, submission_id=models.OuterRef('pk')
        )
        queryset = self.request.event.submissions.filter(
            state__in=[
                SubmissionStates.SUBMITTED,
                SubmissionStates.ACCEPTED,
                SubmissionStates.REJECTED,
                SubmissionStates.CONFIRMED,
            ]
        )
        queryset = self.filter_queryset(queryset)
        return (
            queryset.order_by('review_id')
            .annotate(has_override=models.Exists(overridden_reviews))
            .annotate(
                avg_score=models.Case(
                    models.When(
                        has_override=True,
                        then=self.request.event.settings.review_max_score + 1,
                    ),
                    default=models.Avg('reviews__score'),
                )
            )
            .order_by('-state', '-avg_score', 'code')
        )

    def get_permission_object(self):
        return self.request.event

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        missing_reviews = Review.find_missing_reviews(
            self.request.event, self.request.user
        )
        reviewers = User.objects.filter(
            teams__in=self.request.event.teams.filter(is_reviewer=True)
        ).distinct()
        context['missing_reviews'] = missing_reviews
        context['next_submission'] = missing_reviews.first()
        context['reviewers'] = reviewers.count()
        context['active_reviewers'] = (
            reviewers.filter(reviews__isnull=False)
            .order_by('user__id')
            .distinct()
            .count()
        )
        context['review_count'] = self.request.event.reviews.count()
        if context['active_reviewers'] > 1:
            context['avg_reviews'] = round(
                context['review_count'] / context['active_reviewers'], 1
            )
        return context


class ReviewSubmission(PermissionRequired, CreateOrUpdateView):

    form_class = ReviewForm
    model = Review
    template_name = 'orga/submission/review.html'
    permission_required = 'submission.view_reviews'

    @cached_property
    def submission(self):
        return get_object_or_404(
            self.request.event.submissions, code__iexact=self.kwargs['code']
        )

    @cached_property
    def object(self):
        return (
            self.submission.reviews.exclude(user__in=self.submission.speakers.all())
            .filter(user=self.request.user)
            .first()
        )

    def get_object(self):
        return self.object

    def get_permission_object(self):
        return self.submission

    @cached_property
    def read_only(self):
        return not self.request.user.has_perm(
            'submission.review_submission', self.get_object() or self.submission
        )

    @cached_property
    def qform(self):
        return QuestionsForm(
            target='reviewer',
            event=self.request.event,
            data=(self.request.POST if self.request.method == 'POST' else None),
            files=(self.request.FILES if self.request.method == 'POST' else None),
            speaker=self.request.user,
            review=self.object,
            readonly=self.read_only,
        )

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['submission'] = self.submission
        context['review'] = self.object
        context['read_only'] = self.read_only
        context['qform'] = self.qform
        context['skip_for_now'] = Review.find_missing_reviews(
            self.request.event, self.request.user, ignore=[self.submission]
        ).first()
        context['profiles'] = [
            speaker.event_profile(self.request.event)
            for speaker in self.submission.speakers.all()
        ]
        context['reviews'] = [
            {
                'score': review.display_score,
                'text': review.text,
                'user': review.user.get_display_name(),
                'answers': [
                    review.answers.filter(question=question).first()
                    for question in self.qform.queryset
                ],
            }
            for review in self.submission.reviews.exclude(
                pk=(self.object.pk if self.object else None)
            )
        ]
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        kwargs['user'] = self.request.user
        kwargs['read_only'] = self.read_only
        return kwargs

    def form_valid(self, form):
        if not self.qform.is_valid():
            messages.error(self.request, _('There have been errors with your input.'))
            return redirect(self.get_success_url())
        form.instance.submission = self.submission
        form.instance.user = self.request.user
        if not form.instance.pk:
            if not self.request.user.has_perm(
                'submission.review_submission', self.submission
            ):
                messages.error(
                    self.request, _('You cannot review this submission at this time.')
                )
                return redirect(self.get_success_url())
        if form.instance.pk and not self.request.user.has_perm(
            'submission.edit_review', form.instance
        ):
            messages.error(
                self.request, _('You cannot review this submission at this time.')
            )
            return redirect(self.get_success_url())
        form.save()
        self.qform.review = form.instance
        self.qform.save()
        return super().form_valid(form)

    def get_success_url(self) -> str:
        if self.request.POST.get('show_next', '0').strip() == '1':
            next_submission = Review.find_missing_reviews(
                self.request.event, self.request.user
            ).first()
            if next_submission:
                messages.success(self.request, phrases.orga.another_review)
                return next_submission.orga_urls.reviews
            messages.success(
                self.request, _('Nice, you have no submissions left to review!')
            )
            return self.request.event.orga_urls.reviews
        return self.submission.orga_urls.reviews


class ReviewSubmissionDelete(PermissionRequired, TemplateView):
    template_name = 'orga/review/submission_delete.html'
    permission_required = 'orga.remove_review'

    def get_permission_object(self):
        return self.request.event
