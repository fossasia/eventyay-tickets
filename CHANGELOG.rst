Changelog
=========

This changelog contains the changes to be released in the **next** release.
For older changelogs, please visit our releases_ page.

vx.x.x
------

*Released on 201x-xx-xx*

Breaking Changes
~~~~~~~~~~~~~~~~


Features
~~~~~~~~

- Speakers can now be marked as "arrived". (#243)
- Visitors can download an ical file containing all talks of a single speaker (#67)
- There is now an API for speakers.
- The speaker biography is now shown in submissions in the API endpoint.


Fixed bugs
~~~~~~~~~~~

- Non-superusers could not access the email sending form.
- More than one event stage could be shown as active.
- Trying to look at entered submissions without being logged in produced a server error instead of a 404.


.. _releases: https://github.com/pretalx/pretalx/releases
