Changelog
=========

This changelog contains the changes to be released in the **next** release.
For older changelogs, please visit our releases_ page.

v0.x.x
------

*Released on 201x-xx-xx*

If you use postgresql, please use the package ``psycopg2-binary`` instead of ``psycopg2``, which is now also noted in the dependencies for postgresql.


Breaking Changes
~~~~~~~~~~~~~~~~


Features
~~~~~~~~
- pretalx now features a Plugin API, allowing to install custom plugins. Plugins can add their own exporters, and hook into various plugin hooks to be expanded over the course of this year. Plugins can be enabled or disabled per event. Documentation can be found here: https://docs.pretalx.org/en/latest/developer/plugins/index.html
- Organisers can now decide if reviewers should be required to submit a score or a text with their review. (#340)
- Organisers can provide room-based information for speakers, which will be provided in emails about talk scheduling. (#93)
- The list of submissions is now better searchable. (#318)
- Speakers can now upload an image that will be displayed next to their talk information. (#294)
- Reviewers can now also be asked custom questions during their review, with all capabilities that speaker questions have.
- There are now optional review deadlines, preventing reviews to be added, modified, or removed after a certain date. (#352)
- Individual directories for logs, media, and static files can now be configured via environment variables.
- Organisers can now show information snippets to submitters, or speakers. (#348)
- More environment and configuration variables were added to support customisation of filesystem decisions.
- Allow to filter question statistics by speaker status.

Fixed bugs
~~~~~~~~~~~
- In the dashboard, an incorrect link was given to add new reviewers. (#344)
- The "save" button was missing on the mail settings page. (#341)
- Users could not see (instead not change) their submissions after CfP end, until they were either rejected or accepted. (#333)
- In the <title> tag, the event was displayed twice, once properly and once in a technical representation.
- Various UI fixes and improvements
- Documentation fix: The environment variable for database passwords is ``PRETALX_DB_PASS``, not ``PRETALX_DB_PASSWORD``.
- Unconfirmed talks showed up as empty boxes in the schedule editor.
- Upgrading the privileges of an existing user did not result in an email, since no invitation was required.
- The Docker setup was broken. It is fixed, and a notice of limited support was added to the documentation. (#300)
- The orga view now always uses the event timezone.

.. _releases: https://github.com/pretalx/pretalx/releases
