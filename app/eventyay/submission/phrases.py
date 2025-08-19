from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from eventyay.common.text.phrases import Phrases


class SubmissionPhrases(Phrases, app='submission'):
    # Translators: This string is used to mark anything that has been formally deleted,
    # and can only be shown to organisers with extended access. It's usually placed
    # after the title/object like [this].
    deleted = _('deleted')

    submitted = pgettext_lazy('proposal status', 'submitted')
    in_review = pgettext_lazy('proposal status', 'in review')
    not_accepted = pgettext_lazy('proposal status', 'not accepted')
