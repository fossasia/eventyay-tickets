from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from pretalx.common.text.phrases import Phrases


class SchedulePhrases(Phrases, app="schedule"):
    version = pgettext_lazy("Version of the conference schedule", "Version")
    schedule = pgettext_lazy("Schedule/program of the conference", "Schedule")

    # Translators: Ideally a neutral term that will work for workshop, talks and special
    # formats. Plural, used in headings.
    sessions = _("Sessions")

    # Translators: Ideally a term that is as broad as possible, to refer to anybody who
    # presents/owns a session. This word is also used to differentiate accepted „speakers“
    # from not-yet-accepted „submitters“. Plural, used in headings.
    speakers = _("Speakers")

    first_schedule = _("We released our first schedule!")
    wip_version = _(
        "You are currently viewing the editable schedule version, which is unreleased and may change at any time."
    )
    old_version = _("You are currently viewing an older schedule version.")
    current_version = _(
        'You can find the current version <a href="%(current_url)s">here</a>.'
    )

    # Translators: “tz” is a full timezone name like “Europe/Berlin”
    timezone_hint = _("All times in %(tz)s")

    no_feedback = _("There has been no feedback for this session yet.")
