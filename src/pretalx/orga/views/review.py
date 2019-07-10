from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.shortcuts import get_object_or_404, redirect
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView, TemplateView
from django_context_decorator import context

from pretalx.common.mixins.views import (
    EventPermissionRequired, Filterable, PermissionRequired,
)
from pretalx.common.phrases import phrases
from pretalx.common.views import CreateOrUpdateView
from pretalx.orga.forms import ReviewForm
from pretalx.submission.forms import QuestionsForm, SubmissionFilterForm
from pretalx.submission.models import Review, Submission, SubmissionStates


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
        if limit_tracks:
            tracks = set()
            for team in limit_tracks:
                tracks.update(team.limit_tracks.filter(event=self.request.event))
            queryset = queryset.filter(track__in=tracks)
        queryset = self.filter_queryset(queryset).annotate(review_count=Count('reviews'))

        can_see_all_reviews = self.request.user.has_perm('orga.view_all_reviews', self.request.event)
        overridden_reviews = Review.objects.filter(
            override_vote__isnull=False, submission_id=OuterRef('pk')
        )
        if not can_see_all_reviews:
            overridden_reviews = overridden_reviews.filter(user=self.request.user)

        queryset = (
            queryset.annotate(has_override=Exists(overridden_reviews))
            .select_related('track', 'submission_type')
            .prefetch_related('speakers', 'reviews', 'reviews__user')
        )

        for submission in queryset:
            if can_see_all_reviews:
                submission.current_score = submission.median_score
            else:
                reviews = [review for review in submission.reviews.all() if review.user == self.request.user]
                submission.current_score = None
                if reviews:
                    submission.current_score = reviews[0].score

        return self.sort_queryset(queryset)

    def sort_queryset(self, queryset):
        order_prevalence = {
            'default': ('state', 'current_score', 'code'),
            'score': ('current_score', 'state', 'code'),
            'count': ('review_count', 'code')
        }
        ordering = self.request.GET.get('sort', 'default')
        reverse = True
        if ordering.startswith('-'):
            reverse = False
            ordering = ordering[1:]

        order = order_prevalence.get(ordering, order_prevalence['default'])

        def get_order_tuple(obj):
            return tuple(
                getattr(obj, key)
                if not (key == 'current_score' and obj.current_score is None)
                else 100 * -int(reverse)
                for key in order
            )

        return sorted(
            queryset,
            key=get_order_tuple,
            reverse=reverse,
        )

    @context
    def can_accept_submissions(self):
        return self.request.event.submissions.filter(state=SubmissionStates.SUBMITTED).exists() and self.request.user.has_perm('submission.accept_or_reject_submissions', self.request.event)

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        missing_reviews = Review.find_missing_reviews(
            self.request.event, self.request.user
        )
        result['missing_reviews'] = missing_reviews.count()
        result['next_submission'] = missing_reviews.first()
        return result

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        total = {'accept': 0, 'reject': 0, 'error': 0}
        for key, value in request.POST.items():
            if not key.startswith('s-') or value not in ['accept', 'reject']:
                continue
            pk = key.strip('s-')
            try:
                submission = request.event.submissions.filter(state=SubmissionStates.SUBMITTED).get(pk=pk)
            except (Submission.DoesNotExist, ValueError):
                total['error'] += 1
                continue
            if not request.user.has_perm('submission.' + value + '_submission', submission):
                total['error'] += 1
                continue
            getattr(submission, value)(person=request.user)
            total[value] += 1
        if not total['accept'] and not total['reject'] and not total['error']:
            messages.success(request, _('There was nothing to do.'))
        elif total['accept'] or total['reject']:
            msg = str(_('Success! {accepted} submissions were accepted, {rejected} submissions were rejected.')).format(accepted=total['accept'], rejected=total['reject'])
            if total['error']:
                msg += ' ' + str(_('We were unable to change the state of {count} submissions.')).format(count=total['error'])
            messages.success(request, msg)
        else:
            messages.error(request, str(_('We were unable to change the state of all {count} submissions.')).format(count=total['error']))
        return super().get(request, *args, **kwargs)


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
        result = super().get_context_data(**kwargs)
        result['done'] = self.request.user.reviews.filter(submission__event=self.request.event).count()
        result['total_reviews'] = Review.find_missing_reviews(
            self.request.event, self.request.user
        ).count() + result['done']
        if result['total_reviews']:
            result['percentage'] = int(result['done'] * 100 / result['total_reviews'])
        return result

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


class RegenerateDecisionMails(EventPermissionRequired, TemplateView):
    template_name = 'orga/review/regenerate_decision_mails.html'
    permission_required = 'orga.change_submissions'

    def get_queryset(self):
        return self.request.event.submissions.filter(
            state__in=[SubmissionStates.ACCEPTED, SubmissionStates.REJECTED],
            speakers__isnull=False,
        )

    @context
    @cached_property
    def count(self):
        return self.get_queryset().count()

    def post(self, request, **kwargs):
        for submission in self.get_queryset():
            submission.send_state_mail()
        messages.success(request, _('{count} emails were generated and placed in the outbox.').format(count=self.count))
        return redirect(self.request.event.orga_urls.reviews)
