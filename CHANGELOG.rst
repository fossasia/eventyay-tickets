Changelog
=========

This changelog contains the changes to be released in the **next** release.
For older changelogs, please visit our releases_ page.

vx.y.z
------

*Released on 201x-xx-xx*

This release removes the dependecy `django-zxcvbn-password`. Depending on your setup, you can remove it with `pip uninstall django-zxcvbn-password` or a similar command.

This release also expanded the `rebuild` command to take a flag `--clear`, which discards all existing compiled static files and rebuilds them from scratch. This command invocation is encouraged after an update, if any event on the instance uses custom styling or custom colors.

Breaking Changes
~~~~~~~~~~~~~~~~


Features
~~~~~~~~
- List all currently possible exports in export page.
- Import XML files to release a new schedule. (#322)
- New team management interface to see all team members and permissions in one place. (#292)
- New init command for project setup.
- Remove unused `max_duration` property of submission types. (#327)
- Add `--clear` flag to `rebuild` manage command.
- You can choose a pattern for the header hero strip in your event color.
- You can now choose different datetimes per submission type, overriding the default deadline. (#320)

Fixed bugs
~~~~~~~~~~~
- The schedule export could change project settings, requiring pretalx to be restarted to reset the settings.
- When running pretalx as (in-application) superuser, permission issues could arise. pretalx now warns and offers to migrate the account to an administrator account. (#259)
- Frontend password validation was broken, and never displayed interactive password statistics. This was a display issue only.

.. _releases: https://github.com/pretalx/pretalx/releases
