from django.template.loader import get_template
from django.utils.formats import get_format
from django.utils.timezone import override as tzoverride
from django.utils.translation import override

from pretalx.common.context_processors import get_day_month_date_format


def get_notification_date_format():
    """Call from correct locale context!"""
    return get_day_month_date_format() + ", " + get_format("TIME_FORMAT")


def render_notifications(data, event, speaker=None):
    """Renders the schedule notifications sent to speakers, in the form of a
    Markdown list.

    The data format is expected to be a dict with the keys ``create`` and ``update``,
    each containing a list of TalkSlot objects, as returned by the values of the
    Schedule.speakers.concerned return value."""
    template = get_template("schedule/speaker_notification.txt")
    locale = speaker.get_locale_for_event(event) if speaker else event.locale
    with override(locale), tzoverride(event.tz):
        date_format = get_notification_date_format()
        return template.render({"START_DATE_FORMAT": date_format, **data})


def get_full_notifications(speaker, event):
    """Builds a notification dict for a speaker, pretending that the current schedule
    version is the first one. That is, all talks will be included in the ``create``
    section."""
    if not event.current_schedule:
        return {"create": [], "update": []}
    return {
        "create": event.current_schedule.scheduled_talks.filter(
            submission__speakers=speaker
        ),
        "update": [],
    }


def get_current_notifications(speaker, event):
    empty_result = {"create": [], "update": []}
    if not event.current_schedule:
        return empty_result
    return event.current_schedule.speakers_concerned.get(speaker, empty_result)
