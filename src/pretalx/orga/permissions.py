import rules

from pretalx.person.permissions import is_administrator, is_orga, is_reviewer
from pretalx.submission.permissions import can_be_reviewed, is_review_author


@rules.predicate
def review_deadline_unmet(user, obj):
    from django.utils.timezone import now
    event = obj.event
    deadline = event.settings.review_deadline
    return True if not deadline else now() <= deadline


rules.add_perm('orga.view_orga_area', is_orga | is_reviewer)
rules.add_perm('orga.search_all_users', is_orga)
rules.add_perm('orga.change_settings', is_orga)
rules.add_perm('orga.view_submission_cards', is_orga)
rules.add_perm('orga.edit_cfp', is_orga)
rules.add_perm('orga.view_question', is_orga)
rules.add_perm('orga.edit_question', is_orga)
rules.add_perm('orga.remove_question', is_orga)
rules.add_perm('orga.view_submission_type', is_orga)
rules.add_perm('orga.edit_submission_type', is_orga)
rules.add_perm('orga.remove_submission_type', is_orga)
rules.add_perm('orga.view_mails', is_orga)
rules.add_perm('orga.send_mails', is_orga)
rules.add_perm('orga.edit_mails', is_orga)
rules.add_perm('orga.purge_mails', is_orga)
rules.add_perm('orga.view_mail_templates', is_orga)
rules.add_perm('orga.edit_mail_templates', is_orga)
rules.add_perm('orga.view_review_dashboard', is_orga | is_reviewer)
rules.add_perm('orga.view_reviews', is_reviewer)
rules.add_perm('orga.perform_reviews', is_reviewer & review_deadline_unmet)
rules.add_perm('orga.remove_review', is_administrator | (is_review_author & can_be_reviewed))
rules.add_perm('orga.view_schedule', is_orga)
rules.add_perm('orga.release_schedule', is_orga)
rules.add_perm('orga.edit_schedule', is_orga)
rules.add_perm('orga.schedule_talk', is_orga)
rules.add_perm('orga.view_room', is_orga)
rules.add_perm('orga.edit_room', is_orga)
rules.add_perm('orga.view_speakers', is_orga | is_reviewer)
rules.add_perm('orga.view_speaker', is_orga | is_reviewer)
rules.add_perm('orga.change_speaker', is_orga)
rules.add_perm('orga.view_submissions', is_orga | is_reviewer)
rules.add_perm('orga.create_submission', is_orga)
rules.add_perm('orga.change_submission_state', is_orga)
rules.add_perm('orga.view_information', is_orga | is_reviewer)
rules.add_perm('orga.change_information', is_orga)
