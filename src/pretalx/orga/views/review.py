from django.contrib import messages
from django.db import models
from django.shortcuts import get_object_or_404, redirect
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.views.generic import ListView, TemplateView

from pretalx.common.mixins.views import PermissionRequired
from pretalx.common.views import CreateOrUpdateView
from pretalx.orga.forms import ReviewForm
from pretalx.person.models import EventPermission
from pretalx.submission.models import Review


class ReviewDashboard(PermissionRequired, ListView):
    template_name = 'orga/review/dashboard.html'
    paginate_by = 25
    context_object_name = 'submissions'
    permission_required = 'orga.view_review_dashboard'

    def get_queryset(self, *args, **kwargs):
        overridden_reviews = Review.objects.filter(override_vote__isnull=False, submission_id=models.OuterRef('pk'))
        return self.request.event.submissions\
            .order_by('review_id')\
            .annotate(has_override=models.Exists(overridden_reviews))\
            .annotate(avg_score=models.Case(
                models.When(
                    has_override=True,
                    then=self.request.event.settings.review_max_score + 1,
                ),
                default=models.Avg('reviews__score')
            ))\
            .order_by('-state', '-avg_score')

    def get_permission_object(self):
        return self.request.event

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['missing_reviews'] = Review.find_missing_reviews(self.request.event, self.request.user)
        ctx['reviewers'] = EventPermission.objects.filter(is_reviewer=True, event=self.request.event).count()
        ctx['next_submission'] = Review.find_missing_reviews(self.request.event, self.request.user).first()
        return ctx


class ReviewSubmission(PermissionRequired, CreateOrUpdateView):

    form_class = ReviewForm
    model = Review
    template_name = 'orga/submission/review.html'
    permission_required = 'submission.view_reviews'

    @property
    def submission(self):
        return get_object_or_404(
            self.request.event.submissions,
            code__iexact=self.kwargs['code'],
        )

    def get_object(self):
        return self.submission.reviews.exclude(user__in=self.submission.speakers.all()).filter(user=self.request.user).first()

    def get_permission_object(self):
        return self.submission

    @cached_property
    def read_only(self):
        return not self.request.user.has_perm('submission.review_submission', self.get_object() or self.submission)

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        submission = self.request.event.submissions.get(code__iexact=self.kwargs['code'])
        ctx['submission'] = submission
        ctx['review'] = submission.reviews.filter(user=self.request.user).first()
        ctx['read_only'] = self.read_only
        ctx['override_left'] = self.request.user.remaining_override_votes(self.request.event)
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        kwargs['user'] = self.request.user
        kwargs['read_only'] = self.read_only
        return kwargs

    def form_valid(self, form):
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
        return super().form_valid(form)

    def get_success_url(self) -> str:
        if self.request.POST.get('show_next', '0').strip() == '1':
            next_submission = Review.find_missing_reviews(self.request.event, self.request.user).first()
            if next_submission:
                messages.success(self.request, _('You are on a roll!'))  # TODO: choose from a list of messages
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
