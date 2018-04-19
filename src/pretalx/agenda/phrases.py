from django.utils.translation import ugettext as _

from pretalx.common.phrases import BasePhrases, Phrases


class AgendaPhrases(Phrases, app='agenda'):
    feedback_success = [
        _('Thank you for your feedback!'),
        _('Thanks, we (and our speakers) appreciate your feedback!'),
    ]
    changelog_unchanged = [
        _('Nothing has changed, we just wanted to change the version name. It was going out of style.'),
        _('No changes are visible in this version, but be assured we\'re working on cool new versions behind the scenes.'),
    ]
    changelog_first = [
        _('We released our first schedule!'),
        _('This is where it all began.'),
        _('The first schedule was released.'),
    ]
    changelog_new_talks = _('We have new talks!')
    changelog_new_talk = _('We have a new talk: ')
    changelog_canceled_talks = _('Sadly, we had to cancel talks:')
    changelog_canceled_talk = _('We sadly had to cancel a talk: ')
    changelog_moved_talks = _('We had to move some talks, so if you were planning on seeing them, check their new dates or locations:')
    changelog_moved_talk = _('We have moved a talk around: ')

    feedback = _('Feedback')
    feedback_personal = _('This review is for you personally, not for all speakers in this talk.')
    feedback_empty = _('There has been no feedback for this talk yet.')
    feedback_send = BasePhrases.send + [
        _('Send feedback'),
        _('Send review'),
    ]
    feedback_explanation = _(
        'Reviews are a valuable tool for speakers to improve their content and presentation. '
        'Even a very short review can prove very valuable to a speaker – but we\'d like to ask you to '
        'take the time and find a constructive way to communicate your feedback.'
    )
    feedback_not_now = _('You can\'t give feedback for this talk at this time.')

    schedule_editable = _('You are currently viewing the editable schedule version, which is unreleased and may change at any time.')
    schedule_do_not_record = _('This talk will not be recorded.')
    speaker_other_talks = _('Other talks by this speaker:')
    speaker_other_talk = _('This speaker also holds:')
