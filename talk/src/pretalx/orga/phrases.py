from django.utils.translation import gettext_lazy as _

from pretalx.common.text.phrases import Phrases


class OrgaPhrases(Phrases, app="orga"):
    event_date_start_invalid = _("The event end cannot be before the start.")

    event_header_pattern_label = _("Frontpage header pattern")
    event_header_pattern_help_text = _(
        'Choose how the frontpage header banner will be styled. Pattern source: <a href="http://www.heropatterns.com/">heropatterns.com</a>, CC BY 4.0.'
    )
    event_schedule_format_label = _("Schedule display format")
    proposal_id_help_text = _(
        "The unique ID of a proposal is used in the proposal URL and in exports"
    )
    password_reset_success = _("The password was reset and the user was notified.")
    password_reset_fail = (
        _("The password reset email could not be sent, so the password was not reset."),
    )
    mails_in_outbox = _(
        "{count} emails have been saved to the outbox – you can make individual changes there or just send them all."
    )
