from django.contrib import messages
from django.db.models import Avg, Case, Count, Exists, OuterRef, Q, Subquery, When
from django.shortcuts import get_object_or_404, redirect
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.views.generic import ListView, TemplateView
from django_context_decorator import context

from pretalx.common.mixins.views import (
    EventPermissionRequired, Filterable, PermissionRequired,
)
from pretalx.common.phrases import phrases
from pretalx.common.views import CreateOrUpdateView
from pretalx.orga.forms import ReviewForm
from pretalx.submission.forms import QuestionsForm, SubmissionFilterForm
from pretalx.submission.models import Review, SubmissionStates


class ReviewDashboard(EventPermissionRequired, Filterable, ListView):
    template_name = 'orga/review/dashboard.html'
    paginate_by = None
    context_object_name = 'submissions'
    permission_required = 'orga.view_review_dashboard'
    default_filters = (
        'code__icontains',
        'speakers__name__icontains',
        'title__icontains',
    )
    filter_fields = ('submission_type', 'state', 'track')

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

    def get_queryset(self):
        queryset = self.request.event.submissions.filter(
            state__in=[
                SubmissionStates.SUBMITTED,
                SubmissionStates.ACCEPTED,
                SubmissionStates.REJECTED,
                SubmissionStates.CONFIRMED,
            ]
        )
        limit_tracks = self.request.user.teams.filter(
            Q(all_events=True)
            | Q(
                Q(all_events=False)
                & Q(limit_events__in=[self.request.event])
            ),
            limit_tracks__isnull=False,
        )
        if len(limit_tracks):
            tracks = set()
            for team in limit_tracks:
                tracks.update(team.limit_tracks.filter(event=self.request.event))
            queryset = queryset.filter(track__in=tracks)
        queryset = self.filter_queryset(queryset).annotate(review_count=Count('reviews'))

        can_see_all_reviews = self.request.user.has_perm('orga.view_all_reviews', self.request.event)
        ordering = self.request.GET.get('sort', 'default')

        overridden_reviews = Review.objects.filter(
            override_vote__isnull=False, submission_id=OuterRef('pk')
        )
        default = Avg('reviews__score')

        if not can_see_all_reviews:
            overridden_reviews = overridden_reviews.filter(user=self.request.user)
            user_reviews = self.request.event.reviews.filter(user=self.request.user)
            default = Subquery(user_reviews.filter(submission_id=OuterRef('pk')).values_list('score')[:1])

        queryset = (
            queryset.order_by('review_id')
            .annotate(has_override=Exists(overridden_reviews))
            .annotate(
                avg_score=Case(
                    When(
                        has_override=True,
                        then=self.request.event.settings.review_max_score + 1,
                    ),
                    default=default,
                )
            ).select_related('track').select_related('submission_type').prefetch_related('speakers').prefetch_related('reviews')
        )
        if ordering == 'count':
            return queryset.order_by('review_count', 'code')
        if ordering == '-count':
            return queryset.order_by('-review_count', 'code')
        if ordering == 'score':
            return queryset.order_by('-avg_score', '-state', 'code')
        if ordering == '-score':
            return queryset.order_by('avg_score', '-state', 'code')
        return queryset.order_by('-state', '-avg_score', 'code')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        missing_reviews = Review.find_missing_reviews(
            self.request.event, self.request.user
        )
        context['missing_reviews'] = missing_reviews
        context['next_submission'] = missing_reviews.first()
        return context


class ReviewSubmission(PermissionRequired, CreateOrUpdateView):

    form_class = ReviewForm
    model = Review
    template_name = 'orga/submission/review.html'
    permission_required = 'submission.view_reviews'
    write_permission_required = 'submission.review_submission'

    @context
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

    @context
    @cached_property
    def read_only(self):
        return not self.request.user.has_perm(
            'submission.review_submission', self.get_object() or self.submission
        )

    @context
    def profiles(self):
        return [
            speaker.event_profile(self.request.event)
            for speaker in self.submission.speakers.all()
        ]

    @context
    def reviews(self):
        return [
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

    @context
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

    @context
    def skip_for_now(self):
        return Review.find_missing_reviews(
            self.request.event, self.request.user, ignore=[self.submission]
        ).first()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['done'] = self.request.user.reviews.filter(submission__event=self.request.event).count()
        context['total_reviews'] = Review.find_missing_reviews(
            self.request.event, self.request.user
        ).count() + context['done']
        if context['total_reviews']:
            context['percentage'] = int(context['done'] * 100 / context['total_reviews'])
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


class ReviewSubmissionDelete(EventPermissionRequired, TemplateView):
    template_name = 'orga/review/submission_delete.html'
    permission_required = 'orga.remove_review'
