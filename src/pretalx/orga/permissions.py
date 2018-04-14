import rules

from pretalx.person.permissions import (
    can_change_submissions, is_administrator, is_reviewer,
)
from pretalx.submission.permissions import can_be_reviewed, is_review_author


@rules.predicate
def can_change_event_settings(user, obj):
    return obj.event in user.get_events_for_permission(can_change_event_settings=True)


@rules.predicate
def can_change_organiser_settings(user, obj):
    return obj.event in user.get_events_for_permission(can_change_organiser_settings=True)


@rules.predicate
def can_change_team_settings(user, obj):
    return obj.event in user.get_events_for_permission(can_change_team_settings=True)


@rules.predicate
def review_deadline_unmet(user, obj):
    from django.utils.timezone import now
    event = obj.event
    deadline = event.settings.review_deadline
    return True if not deadline else now() <= deadline


rules.add_perm('orga.view_orga_area', can_change_submissions | is_reviewer)
rules.add_perm('orga.search_all_users', can_change_submissions)
rules.add_perm('orga.change_settings', can_change_event_settings)
rules.add_perm('orga.change_organiser_settings', can_change_organiser_settings)
rules.add_perm('orga.change_team_settings', can_change_team_settings)
rules.add_perm('orga.view_submission_cards', can_change_submissions)
rules.add_perm('orga.edit_cfp', can_change_submissions)
rules.add_perm('orga.view_question', can_change_submissions)
rules.add_perm('orga.edit_question', can_change_submissions)
rules.add_perm('orga.remove_question', can_change_submissions)
rules.add_perm('orga.view_submission_type', can_change_submissions)
rules.add_perm('orga.edit_submission_type', can_change_submissions)
rules.add_perm('orga.remove_submission_type', can_change_submissions)
rules.add_perm('orga.view_mails', can_change_submissions)
rules.add_perm('orga.send_mails', can_change_submissions)
rules.add_perm('orga.edit_mails', can_change_submissions)
rules.add_perm('orga.purge_mails', can_change_submissions)
rules.add_perm('orga.view_mail_templates', can_change_submissions)
rules.add_perm('orga.edit_mail_templates', can_change_submissions)
rules.add_perm('orga.view_review_dashboard', can_change_submissions | is_reviewer)
rules.add_perm('orga.view_reviews', is_reviewer)
rules.add_perm('orga.perform_reviews', is_reviewer & review_deadline_unmet)
rules.add_perm('orga.remove_review', is_administrator | (is_review_author & can_be_reviewed))
rules.add_perm('orga.view_schedule', can_change_submissions)
rules.add_perm('orga.release_schedule', can_change_submissions)
rules.add_perm('orga.edit_schedule', can_change_submissions)
rules.add_perm('orga.schedule_talk', can_change_submissions)
rules.add_perm('orga.view_room', can_change_submissions)
rules.add_perm('orga.edit_room', can_change_submissions)
rules.add_perm('orga.view_speakers', can_change_submissions | is_reviewer)
rules.add_perm('orga.view_speaker', can_change_submissions | is_reviewer)
rules.add_perm('orga.change_speaker', can_change_submissions)
rules.add_perm('orga.view_submissions', can_change_submissions | is_reviewer)
rules.add_perm('orga.create_submission', can_change_submissions)
rules.add_perm('orga.change_submission_state', can_change_submissions)
rules.add_perm('orga.view_information', can_change_submissions | is_reviewer)
rules.add_perm('orga.change_information', can_change_submissions)
