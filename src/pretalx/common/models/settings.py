from django.utils.translation import ugettext_noop
from hierarkey.models import GlobalSettingsBase, Hierarkey
from i18nfield.strings import LazyI18nString

settings_hierarkey = Hierarkey(attribute_name='settings')


@settings_hierarkey.set_global()
class GlobalSettings(GlobalSettingsBase):
    pass


settings_hierarkey.add_default('show_schedule', 'True', bool)
settings_hierarkey.add_default('custom_domain', '', str)

settings_hierarkey.add_default('review_min_score', 0, int)
settings_hierarkey.add_default('review_max_score', 1, int)

settings_hierarkey.add_default('mail_from', 'noreply@example.org', str)
settings_hierarkey.add_default('smtp_use_custom', 'False', bool)
settings_hierarkey.add_default('smtp_host', '', str)
settings_hierarkey.add_default('smtp_port', '587', int)
settings_hierarkey.add_default('smtp_username', '', str)
settings_hierarkey.add_default('smtp_password', '', str)
settings_hierarkey.add_default('smtp_use_tls', 'True', bool)
settings_hierarkey.add_default('smtp_use_ssl', 'False', bool)

settings_hierarkey.add_default('mail_text_reset', LazyI18nString.from_gettext(ugettext_noop("""Hello {name},

you have requested a new password for your submission account at {event}.

To reset your password, click on the following link:

{url}

If this wasn't you, you can just ignore this email.

All the best,
your {event} team.
""")), LazyI18nString)
settings_hierarkey.add_default('mail_on_new_submission', 'False', bool)
settings_hierarkey.add_default('mail_text_new_submission', LazyI18nString.from_gettext(ugettext_noop("""Hi,

you have received a new submission for your event {event_name}:
»{submission_title}« by {speakers}.
You can see details at

  {orga_url}

All the best,
your {event_name} CfP system.
""")), LazyI18nString)
