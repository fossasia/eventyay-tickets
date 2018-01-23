Changelog
=========

This changelog contains the changes to be released in the **next** release.
For older changelogs, please visit our releases_ page.

vx.y.z
------

*Released on 201x-xx-xx*

Breaking Changes
~~~~~~~~~~~~~~~~


Features
~~~~~~~~
- Import XML files to release a new schedule. (#322)
- New team management interface to see all team members and permissions in one place. (#292)
- New init command for project setup.

Fixed bugs
~~~~~~~~~~~
- The schedule export could change project settings, requiring pretalx to be restarted to reset the settings.
- When running pretalx as (in-application) superuser, permission issues could arise. pretalx now warns and offers to migrate the account to an administrator account. (#259)

.. _releases: https://github.com/pretalx/pretalx/releases
