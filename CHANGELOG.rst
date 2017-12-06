Changelog
=========

This changelog contains the changes to be released in the **next** release.
For older changelogs, please visit our releases_ page.

vX.Y.Z
------

*Released on 20XX-XX-XX*

Breaking Changes
~~~~~~~~~~~~~~~~


Features
~~~~~~~~

- Added better meta tags, which leads to better display in social media. (#122)


Fixed bugs
~~~~~~~~~~~

- Inactive questions could not be deleted (making them active first worked as a workaround). (#289)
- Choice questions could not be deleted as long as they still had answer options. (#288)
- Review team invitations sometimes failed, resulting in useless invitation objects.
- When clicking the "Save & next" button when reviewing, an internal error was encountered after the review was saved.
- Reviewers could not be removed from their team.
- URLs were always generated with 'localhost' as their host.


.. _releases: https://github.com/pretalx/pretalx/releases
