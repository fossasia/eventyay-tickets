import rules
from django.db.models import Count, Exists, OuterRef, Q, Subquery

from .person import is_only_reviewer, is_reviewer


@rules.predicate
def reviewer_can_create_tags(user, obj):
    event = obj.event
    return bool(event.active_review_phase and event.active_review_phase.can_tag_submissions == 'create_tags')


@rules.predicate
def reviewer_can_change_submissions(user, obj):
    return bool(obj.event.active_review_phase and obj.event.active_review_phase.can_change_submission_state)


@rules.predicate
def reviewer_can_change_tags(user, obj):
    event = obj.event
    return bool(event.active_review_phase and event.active_review_phase.can_tag_submissions == 'use_tags')


@rules.predicate
def orga_can_change_submissions(user, obj):
    event = getattr(obj, 'event', None)
    if not user or user.is_anonymous or not obj or not event:
        return False
    if user.is_administrator:
        return True
    return 'can_change_submissions' in user.get_permissions_for_event(event)


orga_can_view_submissions = orga_can_change_submissions | is_reviewer
orga_or_reviewer_can_change_submission = orga_can_change_submissions | (is_reviewer & reviewer_can_change_submissions)


@rules.predicate
def is_cfp_open(user, obj):
    event = getattr(obj, 'event', None)
    return event and event.is_public and event.cfp.is_open


@rules.predicate
def are_featured_submissions_visible(user, event):
    from eventyay.talk_rules.agenda import is_agenda_visible

    show_featured = event.get_feature_flag('show_featured')
    if not event.is_public or show_featured == 'never':
        return False
    if show_featured == 'always':
        return True
    return (not is_agenda_visible(user, event)) or not event.current_schedule


@rules.predicate
def use_tracks(user, obj):
    event = obj.event
    return event.get_feature_flag('use_tracks')


@rules.predicate
def is_speaker(user, obj):
    obj = getattr(obj, 'submission', obj)
    return obj and user in obj.speakers.all()


@rules.predicate
def can_be_withdrawn(user, obj):
    from eventyay.base.models import SubmissionStates

    return obj and SubmissionStates.WITHDRAWN in SubmissionStates.valid_next_states.get(obj.state, [])


@rules.predicate
def can_be_rejected(user, obj):
    from eventyay.base.models import SubmissionStates

    return obj and SubmissionStates.REJECTED in SubmissionStates.valid_next_states.get(obj.state, [])


@rules.predicate
def can_be_accepted(user, obj):
    from eventyay.base.models import SubmissionStates

    return obj and SubmissionStates.ACCEPTED in SubmissionStates.valid_next_states.get(obj.state, [])


@rules.predicate
def can_be_confirmed(user, obj):
    from eventyay.base.models import SubmissionStates

    return obj and SubmissionStates.CONFIRMED in SubmissionStates.valid_next_states.get(obj.state, [])


@rules.predicate
def can_be_canceled(user, obj):
    from eventyay.base.models import SubmissionStates

    return obj and SubmissionStates.CANCELED in SubmissionStates.valid_next_states.get(obj.state, [])


@rules.predicate
def can_be_removed(user, obj):
    from eventyay.base.models import SubmissionStates

    return obj and SubmissionStates.DELETED in SubmissionStates.valid_next_states.get(obj.state, [])


@rules.predicate
def can_be_edited(user, obj):
    return obj and obj.editable


@rules.predicate
def can_request_speakers(user, submission):
    from eventyay.base.models import SubmissionStates

    return submission.state != SubmissionStates.DRAFT and submission.event.cfp.request_additional_speaker


@rules.predicate
def reviews_are_open(user, obj):
    event = obj.event
    return bool(event.active_review_phase and event.active_review_phase.can_review)


@rules.predicate
def can_view_all_reviews(user, obj):
    event = obj.event
    return bool(event.active_review_phase and event.active_review_phase.can_see_other_reviews == 'always')


@rules.predicate
def can_view_reviewer_names(user, obj):
    event = obj.event
    return bool(event.active_review_phase and event.active_review_phase.can_see_reviewer_names)


@rules.predicate
def can_view_reviews(user, obj):
    if can_view_all_reviews(user, obj):
        return True
    phase = obj.event.active_review_phase
    return bool(phase and phase.can_see_other_reviews == 'after_review' and obj.reviews.filter(user=user).exists())


@rules.predicate
def can_be_reviewed(user, obj):
    from eventyay.base.models import SubmissionStates

    if not obj:
        return False
    obj = getattr(obj, 'submission', obj)
    phase = obj.event.active_review_phase and obj.event.active_review_phase.can_review
    state = obj.state == SubmissionStates.SUBMITTED
    return bool(state and phase)


@rules.predicate
def has_reviewer_access(user, obj):
    obj = getattr(obj, 'submission', obj)
    if not obj or not obj.event or not obj.event.active_review_phase:
        return False
    if obj.event.active_review_phase.proposal_visibility == 'all':
        return obj.event.teams.filter(
            Q(limit_tracks__isnull=True) | Q(limit_tracks__in=[obj.track]),
            members__in=[user],
            is_reviewer=True,
        ).exists()
    return user in obj.assigned_reviewers.all()


def questions_for_user(event, user):
    """Used to retrieve synced querysets in the orga list and the API list."""
    from django.db.models import Q

    from eventyay.base.models import TalkQuestionTarget
    from eventyay.talk_rules.orga import can_view_speaker_names

    if user.has_perm('submission.update_question', event):
        # Organizers with edit permissions can see everything
        return event.talkquestions(manager='all_objects').all()
    if not user.is_anonymous and is_only_reviewer(user, event) and can_view_speaker_names(user, event):
        return event.talkquestions(manager='all_objects').filter(
            Q(is_visible_to_reviewers=True) | Q(target=TalkQuestionTarget.REVIEWER),
            active=True,
        )
    if user.has_perm('submission.orga_list_question', event):
        # Other team members can either view all active talkquestions
        # or only talkquestions open to reviewers
        return event.talkquestions(manager='all_objects').all()

    # Now we are left with anonymous users or users with very limited permissions.
    # They can see all public (non-reviewer) talkquestions if they are already publicly
    # visible in the schedule. Otherwise, nothing.
    if user.has_perm('submission.list_question', event):
        return event.talkquestions.all().filter(is_public=True)
    return event.talkquestions.none()


def annotate_assigned(queryset, event, user):
    assigned = user.assigned_reviews.filter(event=event, pk=OuterRef('pk'))
    return queryset.annotate(is_assigned=Exists(Subquery(assigned)))


def get_reviewer_tracks(event, user):
    teams = event.teams.filter(members__in=[user], limit_tracks__isnull=False).prefetch_related(
        'limit_tracks', 'limit_tracks__event'
    )
    tracks = set()
    for team in teams:
        tracks.update(team.limit_tracks.filter(event=event))
    return tracks


def limit_for_reviewers(queryset, event, user, reviewer_tracks=None, add_assignments=False):
    if not (phase := event.active_review_phase):
        queryset = event.submissions.none()
    queryset = queryset.exclude(speakers__in=[user])
    if phase and phase.proposal_visibility == 'assigned':
        queryset = annotate_assigned(queryset, event, user)
        return queryset.filter(is_assigned__gte=1)
    if add_assignments:
        queryset = annotate_assigned(queryset, event, user)
    if reviewer_tracks is None:
        reviewer_tracks = get_reviewer_tracks(event, user)
    if reviewer_tracks:
        return queryset.filter(track__in=reviewer_tracks)
    return queryset


def submissions_for_user(event, user):
    if not user.is_anonymous:
        if is_only_reviewer(user, event):
            return limit_for_reviewers(event.submissions.all(), event, user)
        if user.has_perm('submission.orga_list_submission', event):
            return event.submissions.all()

    # Fall through: both anon users and users without permissions
    # get here, e.g. speakers or attendees.
    if user.has_perm('schedule.list_schedule', event):
        return event.current_schedule.slots
    return event.submissions.none()


@rules.predicate
def is_wip(user, obj):
    schedule = getattr(obj, 'schedule', None) or obj
    return not schedule.version


@rules.predicate
def is_feedback_ready(user, obj):
    return obj.does_accept_feedback


@rules.predicate
def is_break(user, obj):
    return not obj.submission


@rules.predicate
def is_review_author(user, obj):
    return obj and obj.user == user


@rules.predicate
def is_comment_author(user, obj):
    return obj and obj.user == user


@rules.predicate
def submission_comments_active(user, obj):
    return obj.event.get_feature_flag('use_submission_comments')


def speaker_profiles_for_user(event, user, submissions=None):
    submissions = submissions or submissions_for_user(event, user)
    from eventyay.base.models import SpeakerProfile, User

    return SpeakerProfile.objects.filter(event=event, user__in=User.objects.filter(submissions__in=submissions))


def get_reviewable_submissions(event, user, queryset=None):
    """Returns all submissions the user is permitted to review.

    Excludes submissions this user has submitted, and takes track team permissions,
    assignments and review phases into account. The result is ordered by review count.
    """
    from eventyay.base.models import SubmissionStates

    if queryset is None:
        queryset = event.submissions.filter(state=SubmissionStates.SUBMITTED)
    queryset = limit_for_reviewers(queryset, event, user, add_assignments=True)
    queryset = queryset.annotate(review_count=Count('reviews'))
    # This is not randomised, because order_by("review_count", "?") sets all annotated
    # review_count values to 1.
    return queryset.order_by('-is_assigned', 'review_count')


def get_missing_reviews(event, user, ignore=None):
    from eventyay.base.models import SubmissionStates

    queryset = event.submissions.filter(state=SubmissionStates.SUBMITTED).exclude(reviews__user=user)
    if ignore:
        queryset = queryset.exclude(pk__in=ignore)
    return get_reviewable_submissions(event, user, queryset=queryset)
