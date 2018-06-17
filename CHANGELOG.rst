Changelog
=========

This changelog contains the changes to be released in the **next** release.
For older changelogs, please visit our releases_ page.

vx.x.x
------

*Released on 2018-xx-xx*


Breaking Changes
~~~~~~~~~~~~~~~~

None.

Features
~~~~~~~~

- The API now exports links to submission images and speaker avatars.
- Organisers can configure a list of talks to be shown as "sneak peek" before the first schedule is released.
- Submitters can share a submission via a read-only link.
- There is now a navigation search, allowing you to go directly to a range of useful pages.
- Some more context sensitive dashboard tiles were added, for example a countdown to the CfP end.
- You can now configure the configuration file to be read with the ``PRETALX_CONFIG_FILE`` environment variable.

Fixed bugs
~~~~~~~~~~~

- An issue resulting in an empty HTML export was fixed.
- HTML exports failed if a talk was canceled.
- When accessing a confirmation link unauthenticated, a 404 page was shown instead of a login page.
- The API always showed the speaker biography as empty.
- The "Mark speaker arrived" button is now only shown during and slightly before the event. (#441)
- If an event had a custom domain configured, absolute urls would still use the instance's default domain. (#446)
- Removing a speaker from a submission could be impossible if their nick contained special characters.
- If two organisers set a submission to 'accepted' at roughly the same time, two acceptance emails were put into the outbox. (#444)

.. _releases: https://github.com/pretalx/pretalx/releases
