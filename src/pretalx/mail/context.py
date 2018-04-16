from django.utils.translation import ugettext_lazy as _


def get_context_explanation():
    return [
        {
            'name': 'confirmation_link',
            'explanation': _('Link to confirm a submission after it has been accepted.'),
        },
        {
            'name': 'event_name',
            'explanation': _('The event\'s full name.'),
        },
        {
            'name': 'submission_title',
            'explanation': _('The title of the submission in question. Only usable in default templates.'),
        },
        {
            'name': 'submission_url',
            'explanation': _('The link to a submission. Only usable in default templates.'),
        },
        {
            'name': 'speakers',
            'explanation': _('The name(s) of all speakers in this submission.'),
        },
    ]


def template_context_from_event(event):
    return {'all_submissions_url': event.urls.user_submissions.full()}


def template_context_from_submission(submission):
    context = template_context_from_event(submission.event)
    context.update({
        'confirmation_link': submission.urls.confirm.full(),
        'event_name': submission.event.name,
        'submission_title': submission.title,
        'submission_url': submission.urls.user_base.full(),
        'speakers': submission.display_speaker_names,
        'orga_url': submission.orga_urls.base.full(),
    })
    return context
