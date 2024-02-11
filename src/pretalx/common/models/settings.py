import datetime as dt
import json
import uuid

from django.utils.translation import gettext_noop
from hierarkey.models import GlobalSettingsBase, Hierarkey
from i18nfield.strings import LazyI18nString

hierarkey = Hierarkey(attribute_name="settings")


INSTANCE_IDENTIFIER = None


@hierarkey.set_global()
class GlobalSettings(GlobalSettingsBase):
    def get_instance_identifier(self):
        global INSTANCE_IDENTIFIER

        if INSTANCE_IDENTIFIER:
            return INSTANCE_IDENTIFIER

        try:
            INSTANCE_IDENTIFIER = uuid.UUID(self.settings.get("instance_identifier"))
        except (TypeError, ValueError):
            INSTANCE_IDENTIFIER = uuid.uuid4()
            self.settings.set("instance_identifier", str(INSTANCE_IDENTIFIER))
        return INSTANCE_IDENTIFIER


def i18n_unserialise(value):
    try:
        return LazyI18nString(json.loads(value))
    except ValueError:
        return LazyI18nString(str(value))


hierarkey.add_type(
    LazyI18nString, serialize=lambda s: json.dumps(s.data), unserialize=i18n_unserialise
)


hierarkey.add_default("update_check_ack", "False", bool)
hierarkey.add_default("update_check_email", "", str)
hierarkey.add_default("update_check_enabled", "True", bool)
hierarkey.add_default("update_check_result", None, dict)
hierarkey.add_default("update_check_result_warning", "False", bool)
hierarkey.add_default("update_check_last", None, dt.datetime)
hierarkey.add_default("update_check_id", None, str)

hierarkey.add_default("sent_mail_event_created", "False", bool)
hierarkey.add_default("sent_mail_cfp_closed", "False", bool)
hierarkey.add_default("sent_mail_event_over", "False", bool)

hierarkey.add_default(
    "review_help_text",
    LazyI18nString.from_gettext(
        gettext_noop(
            "Please give a fair review on why you'd like to see this proposal at the conference, or why you think it would not be a good fit."
        )
    ),
    LazyI18nString,
)
hierarkey.add_default(
    "mail_text_new_submission",
    LazyI18nString.from_gettext(
        gettext_noop(
            """Hi,

you have received a new proposal for your event {event_name}:
“{submission_title}” by {speakers}.
You can see details at

  {orga_url}

All the best,
your {event_name} CfP system.
"""
        )
    ),
    LazyI18nString,
)
hierarkey.add_default(
    "mail_text_event_created",
    LazyI18nString.from_gettext(
        gettext_noop(
            """Hi,

we hope you're happy with pretalx as your event's CfP system.
These links may be helpful in the coming days and weeks:

- Your event's dashboard: {event_dashboard}
- A list of proposals: {event_submissions}
- Your schedule editor: {event_schedule}

If there is anything you're missing, come tell us about it
at https://github.com/pretalx/pretalx/issues/new or via an
email to support@pretalx.com!
"""
        )
    ),
    LazyI18nString,
)
hierarkey.add_default(
    "mail_text_cfp_closed",
    LazyI18nString.from_gettext(
        gettext_noop(
            """Hi,

just writing you to let you know that your Call for Participation is now
closed. Here is a list of links that should be useful in the next days:

- You'll find a list of all your {submission_count} proposals here:
  {event_submissions}
- You can add reviewers here:
  {event_team}
- You can review proposals here:
  {event_review}
- And create your schedule here, once you have accepted proposals:
  {event_schedule}
"""
        )
    ),
    LazyI18nString,
)
hierarkey.add_default(
    "mail_text_event_over",
    LazyI18nString.from_gettext(
        gettext_noop(
            """Hi,

congratulations, your event is over! Hopefully it went well. Here are some
statistics you might find interesting:

- You had {submission_count} proposals,
- Of which you selected {talk_count} sessions.
- The reviewers wrote {review_count} reviews.
- You released {schedule_count} schedules in total.
- Over the course of the event, you sent {mail_count} mails.

If there is anything you're missing, come tell us about it
at https://github.com/pretalx/pretalx/issues/new or via an
email to support@pretalx.com!
"""
        )
    ),
    LazyI18nString,
)
