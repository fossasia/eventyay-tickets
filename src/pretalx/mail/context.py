def template_context_from_submission(submission):
    return {
        'confirmation_link': 'TODO',
        'event_name': submission.event.name,
        'submission_title': submission.title,
        'submission_url': reverse('cfp:event.user.submissions.edit', event=submission.event.slug, pk=submission.pk),
    }
