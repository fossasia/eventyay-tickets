from django.urls import reverse
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
            'name': 'submission_link',
            'explanation': _('The link to a submission. Only usable in default templates.'),
        },
        {
            'name': 'all_submissions_url',
            'explanation': _('The link to all submissions of this user.'),
        },
    ]


def template_context_from_event(event):
    return {
        'all_submissions_url': reverse(
            'cfp:event.user.submissions',
            kwargs={'event': event.slug}
        ),
    }


def template_context_from_submission(submission):
    ctx = template_context_from_event(submission.event)
    ctx.update({
        'confirmation_link': 'TODO',
        'event_name': submission.event.name,
        'submission_title': submission.title,
        'submission_url': reverse(
            'cfp:event.user.submission.edit',
            kwargs={'event': submission.event.slug, 'id': submission.pk}
        ),
    })
    return ctx
