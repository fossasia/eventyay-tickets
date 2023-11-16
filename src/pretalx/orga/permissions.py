import datetime as dt

import rules
from django.utils.timezone import now

from pretalx.person.permissions import (
    can_change_submissions,
    is_administrator,
    is_reviewer,
)
from pretalx.submission.permissions import (
    can_be_reviewed,
    can_view_all_reviews,
    can_view_reviews,
    is_review_author,
    reviewer_can_change_submissions,
)


@rules.predicate
def can_change_event_settings(user, obj):
    event = getattr(obj, "event", None)
    if not user or user.is_anonymous or not obj or not event:
        return False
    if user.is_administrator:
        return True
    team_permissions = user.team_permissions.get(event.slug)
    if team_permissions is not None:
        return "can_change_event_settings" in team_permissions
    return event.teams.filter(
        members__in=[user], can_change_event_settings=True
    ).exists()


@rules.predicate
def can_change_organiser_settings(user, obj):
    event = getattr(obj, "event", None)
    if event:
        obj = event.organiser
    return (
        user.is_administrator
        or user.teams.filter(organiser=obj, can_change_organiser_settings=True).exists()
    )


@rules.predicate
def can_change_any_organiser_settings(user, obj):
    return not user.is_anonymous and (
        user.is_administrator
        or user.teams.filter(can_change_organiser_settings=True).exists()
    )


@rules.predicate
def can_create_events(user, obj):
    return user.is_administrator or user.teams.filter(can_create_events=True).exists()


@rules.predicate
def can_change_teams(user, obj):
    from pretalx.event.models import Organiser, Team

    if isinstance(obj, Team):
        obj = obj.organiser
    if isinstance(obj, Organiser):
        return user.teams.filter(organiser=obj, can_change_teams=True).exists()
    event = getattr(obj, "event", None)
    if not user or user.is_anonymous or not obj or not event:
        return False
    if user.is_administrator:
        return True
    team_permissions = user.team_permissions.get(event.slug)
    if team_permissions is not None:
        return "can_change_teams" in team_permissions
    return event.teams.filter(members__in=[user], can_change_teams=True).exists()


@rules.predicate
def reviews_are_open(user, obj):
    event = obj.event
    return event.active_review_phase and event.active_review_phase.can_review


@rules.predicate
def can_edit_mail(user, obj):
    return getattr(obj, "sent", False) is None


@rules.predicate
def can_mark_speakers_arrived(user, obj):
    event = obj.event
    return (event.date_from - dt.timedelta(days=1)) <= now().date() <= event.date_to


@rules.predicate
def can_view_speaker_names(user, obj):
    """ONLY in use with users who don't have change permissions."""
    event = obj.event
    reviewer_teams = obj.event.teams.filter(members__in=[user], is_reviewer=True)
    if reviewer_teams and all(
        [team.force_hide_speaker_names for team in reviewer_teams]
    ):
        return False
    return event.active_review_phase and event.active_review_phase.can_see_speaker_names


@rules.predicate
def can_view_reviewer_names(user, obj):
    event = obj.event
    return (
        event.active_review_phase and event.active_review_phase.can_see_reviewer_names
    )


@rules.predicate
def can_add_tags(user, obj):
    event = obj.event
    return (
        event.active_review_phase
        and event.active_review_phase.can_tag_submissions == "create_tags"
    )


@rules.predicate
def can_change_tags(user, obj):
    event = obj.event
    return (
        event.active_review_phase
        and event.active_review_phase.can_tag_submissions == "use_tags"
    )


rules.add_perm(
    "orga.view_orga_area",
    can_change_submissions | can_change_event_settings | is_reviewer,
)
rules.add_perm("orga.change_settings", can_change_event_settings)
rules.add_perm("orga.change_organiser_settings", can_change_organiser_settings)
rules.add_perm("orga.view_organisers", can_change_any_organiser_settings)
rules.add_perm("orga.change_teams", is_administrator | can_change_teams)
rules.add_perm("orga.view_submission_cards", can_change_submissions)
rules.add_perm("orga.edit_cfp", can_change_event_settings)
rules.add_perm("orga.view_question", can_change_submissions)
rules.add_perm("orga.edit_question", can_change_event_settings)
rules.add_perm("orga.remove_question", can_change_event_settings)
rules.add_perm("orga.view_submission_type", can_change_submissions)
rules.add_perm("orga.edit_submission_type", can_change_event_settings)
rules.add_perm("orga.remove_submission_type", can_change_event_settings)
rules.add_perm("orga.view_tracks", can_change_submissions)
rules.add_perm("orga.view_track", can_change_submissions)
rules.add_perm("orga.edit_track", can_change_event_settings)
rules.add_perm("orga.remove_track", can_change_event_settings)
rules.add_perm("orga.add_tags", can_change_submissions | (is_reviewer & can_add_tags))
rules.add_perm(
    "orga.edit_tags", can_change_submissions | (is_reviewer & can_change_tags)
)
rules.add_perm(
    "orga.remove_tags", can_change_submissions | (is_reviewer & can_change_tags)
)
rules.add_perm("orga.view_access_codes", can_change_submissions)
rules.add_perm("orga.view_access_code", can_change_submissions)
rules.add_perm("orga.edit_access_code", can_change_event_settings)
rules.add_perm("orga.remove_access_code", can_change_event_settings)
rules.add_perm("orga.view_mails", can_change_submissions)
rules.add_perm("orga.send_mails", can_change_submissions)
rules.add_perm("orga.send_reviewer_mails", can_change_teams)
rules.add_perm("orga.edit_mails", can_change_submissions & can_edit_mail)
rules.add_perm("orga.purge_mails", can_change_submissions)
rules.add_perm("orga.view_mail_templates", can_change_submissions)
rules.add_perm("orga.edit_mail_templates", can_change_submissions)
rules.add_perm("orga.view_review_dashboard", can_change_submissions | is_reviewer)
rules.add_perm(
    "orga.view_reviews", can_change_submissions | (is_reviewer & can_view_reviews)
)
rules.add_perm(
    "orga.view_all_reviews",
    can_change_submissions | (is_reviewer & can_view_all_reviews),
)
rules.add_perm("orga.perform_reviews", is_reviewer & reviews_are_open)
rules.add_perm(
    "orga.remove_review", is_administrator | (is_review_author & can_be_reviewed)
)
rules.add_perm(
    "orga.view_schedule",
    can_change_submissions | (is_reviewer & can_view_speaker_names),
)
rules.add_perm("orga.release_schedule", can_change_submissions)
rules.add_perm("orga.edit_schedule", can_change_submissions)
rules.add_perm("orga.schedule_talk", can_change_submissions)
rules.add_perm("orga.view_room", can_change_submissions)
rules.add_perm("orga.edit_room", can_change_submissions)
rules.add_perm(
    "orga.view_speakers",
    can_change_submissions | (is_reviewer & can_view_speaker_names),
)
rules.add_perm(
    "orga.view_speaker", can_change_submissions | (is_reviewer & can_view_speaker_names)
)
rules.add_perm(
    "orga.view_reviewer_names",
    can_change_submissions | (is_reviewer & can_view_reviewer_names),
)
rules.add_perm("orga.change_speaker", can_change_submissions)
rules.add_perm("orga.view_submissions", can_change_submissions | is_reviewer)
rules.add_perm("orga.create_submission", can_change_submissions)
rules.add_perm("orga.change_submissions", can_change_submissions)
rules.add_perm(
    "orga.change_submission_state",
    can_change_submissions | (is_reviewer & reviewer_can_change_submissions),
)
rules.add_perm("orga.view_information", can_change_submissions)
rules.add_perm("orga.change_information", can_change_event_settings)
rules.add_perm("orga.create_events", can_create_events)
rules.add_perm("orga.change_plugins", can_change_event_settings)
rules.add_perm(
    "orga.mark_speakers_arrived", can_change_submissions & can_mark_speakers_arrived
)
rules.add_perm("orga.see_speakers_arrival", can_change_submissions)
