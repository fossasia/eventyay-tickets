from django.utils.translation import gettext_lazy as _

from pretalx.common.text.phrases import Phrases


class AgendaPhrases(Phrases, app="agenda"):
    feedback_success = [
        _("Thank you for your feedback!"),
        _("Thanks, we (and our speakers) appreciate your feedback!"),
    ]
    schedule_do_not_record = _("This session will not be recorded.")

    view_schedule = _("View conference schedule")
    view_schedule_preview = _("View schedule preview")
    view_own_submissions = _("Edit or view your proposals")
