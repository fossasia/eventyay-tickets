import json
import uuid
from datetime import datetime

from django.utils.translation import ugettext_noop
from hierarkey.models import GlobalSettingsBase, Hierarkey
from i18nfield.strings import LazyI18nString

hierarkey = Hierarkey(attribute_name='settings')


@hierarkey.set_global()
class GlobalSettings(GlobalSettingsBase):
    def get_instance_identifier(self):
        instance_identifier = self.settings.get('instance_identifier')
        if not instance_identifier:
            instance_identifier = uuid.uuid4()
            self.settings.set('instance_identifier', str(instance_identifier))
        else:
            instance_identifier = uuid.UUID(instance_identifier)
        return instance_identifier


def i18n_unserialise(value):
    try:
        return LazyI18nString(json.loads(value))
    except ValueError:
        return LazyI18nString(str(value))


hierarkey.add_type(
    LazyI18nString, serialize=lambda s: json.dumps(s.data), unserialize=i18n_unserialise
)


hierarkey.add_default('show_on_dashboard', 'True', bool)
hierarkey.add_default('show_schedule', 'True', bool)
hierarkey.add_default('show_sneak_peek', 'True', bool)
hierarkey.add_default('export_html_on_schedule_release', 'True', bool)
hierarkey.add_default('custom_domain', '', str)

hierarkey.add_default('display_header_pattern', '', str)

hierarkey.add_default('cfp_request_abstract', 'True', bool)
hierarkey.add_default('cfp_request_description', 'True', bool)
hierarkey.add_default('cfp_request_biography', 'True', bool)
hierarkey.add_default('cfp_request_notes', 'True', bool)
hierarkey.add_default('cfp_request_do_not_record', 'True', bool)
hierarkey.add_default('cfp_request_image', 'True', bool)

hierarkey.add_default('cfp_require_abstract', 'True', bool)
hierarkey.add_default('cfp_require_description', 'False', bool)
hierarkey.add_default('cfp_require_biography', 'True', bool)
hierarkey.add_default('cfp_require_notes', 'False', bool)
hierarkey.add_default('cfp_require_do_not_record', 'False', bool)
hierarkey.add_default('cfp_require_image', 'False', bool)

hierarkey.add_default('cfp_abstract_min_length', None, int)
hierarkey.add_default('cfp_description_min_length', None, int)
hierarkey.add_default('cfp_biography_min_length', None, int)
hierarkey.add_default('cfp_abstract_max_length', None, int)
hierarkey.add_default('cfp_description_max_length', None, int)
hierarkey.add_default('cfp_biography_max_length', None, int)

hierarkey.add_default('allow_override_votes', 'False', bool)
hierarkey.add_default('review_min_score', 0, int)
hierarkey.add_default('review_max_score', 1, int)
hierarkey.add_default('review_score_mandatory', 'False', bool)
hierarkey.add_default('review_text_mandatory', 'False', bool)
hierarkey.add_default('review_deadline', None, datetime)
hierarkey.add_default(
    'review_help_text',
    LazyI18nString.from_gettext(
        ugettext_noop(
            "Please give a fair review on why you'd like to see this submission at the conference, or why you think it would not be a good fit."
        )
    ),
    LazyI18nString,
)

hierarkey.add_default('mail_from', '', str)
hierarkey.add_default('mail_subject_prefix', '', str)
hierarkey.add_default('mail_signature', '', str)
hierarkey.add_default('smtp_use_custom', 'False', bool)
hierarkey.add_default('smtp_host', '', str)
hierarkey.add_default('smtp_port', '587', int)
hierarkey.add_default('smtp_username', '', str)
hierarkey.add_default('smtp_password', '', str)
hierarkey.add_default('smtp_use_tls', 'True', bool)
hierarkey.add_default('smtp_use_ssl', 'False', bool)

hierarkey.add_default(
    'mail_text_reset',
    LazyI18nString.from_gettext(
        ugettext_noop(
            """Hello {name},

you have requested a new password for your submission account at {event}.

To reset your password, click on the following link:

{url}

If this wasn't you, you can just ignore this email.

All the best,
your {event} team.
"""
        )
    ),
    LazyI18nString,
)
hierarkey.add_default('mail_on_new_submission', 'False', bool)
hierarkey.add_default(
    'mail_text_new_submission',
    LazyI18nString.from_gettext(
        ugettext_noop(
            """Hi,

you have received a new submission for your event {event_name}:
»{submission_title}« by {speakers}.
You can see details at

  {orga_url}

All the best,
your {event_name} CfP system.
"""
        )
    ),
    LazyI18nString,
)

hierarkey.add_default('sent_mail_event_created', 'False', bool)
hierarkey.add_default('sent_mail_cfp_closed', 'False', bool)
hierarkey.add_default('sent_mail_event_over', 'False', bool)
hierarkey.add_default(
    'mail_text_event_created',
    LazyI18nString.from_gettext(
        ugettext_noop(
            """Hi,

we hope you're happy with pretalx as your event's CfP system.
These links may be helpful in the coming days and weeks:

- Your event's dashboard: {event_dashboard}
- A list of submissions: {event_submissions}
- Your schedule editor: {event_schedule}

If there is anything you're missing, come tell us about it
at https://github.com/pretalx/pretalx/issues/new or via an
email to mailto:rixx@cutebit.de!
"""
        )
    ),
    LazyI18nString,
)
hierarkey.add_default(
    'mail_text_cfp_closed',
    LazyI18nString.from_gettext(
        ugettext_noop(
            """Hi,

just writing you to let you know that your Call for Participation is now
closed. You'll find a list of all your {submission_count} submissions here:
{event_submissions}

You can add reviewers here: {event_team}
You can review submissions here: {event_review}
And create your schedule here, once you have accepted submissions: {event_schedule}
"""
        )
    ),
    LazyI18nString,
)
hierarkey.add_default(
    'mail_text_event_over',
    LazyI18nString.from_gettext(
        ugettext_noop(
            """Hi,

congratulations, your event is over! Hopefully it went well. Here are some
statistics you might find interesting:

- You had {submission_count} talk submissions,
- Of which you selected {talk_count} talks.
- The reviewers wrote {review_count} reviews.
- You released {schedule_count} schedules in total.
- Over the course of the event, you sent {mail_count} mails.

If there is anything you're missing, come tell us about it
at https://github.com/pretalx/pretalx/issues/new or via an
email to mailto:rixx@cutebit.de!
"""
        )
    ),
    LazyI18nString,
)
