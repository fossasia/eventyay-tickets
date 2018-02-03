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
- There is now a page in the organiser area listing and linking all currently possible data exports in one export page.
- You may now import XML files to release a new schedule. (#322)
- We added a new team management interface to manage all team members and permissions in one place. (#292)
- There is an `init` command for project setup. Currently it only adds the initial user, but in time it should ask for basic configuration, aswell.
- The `rebuild` command now supports a `--clear` flag to remove all static assets prior to the rebuild.
- You can choose a pattern for the header hero strip in your event color.
- You can now choose different deadlines per submission type, overriding the default deadline. (#320)

Fixed bugs
~~~~~~~~~~~
- The schedule export could change project settings, requiring pretalx to be restarted to reset the settings. This could be avoided by unchecking "Generate HTML export on schedule release".
- When running pretalx as (in-application) superuser, permission issues could arise. pretalx now warns and offers to migrate the account to an administrator account. (#259)
- Frontend password validation was broken, and never displayed interactive password statistics. This was a display issue only.
- We removed the unused `max_duration` property of submission types. (#327)
- Users always saw the default submission type instead of their chosen one. (#329)

.. _releases: https://github.com/pretalx/pretalx/releases
