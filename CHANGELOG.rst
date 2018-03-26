Changelog
=========

This changelog contains the changes to be released in the **next** release.
For older changelogs, please visit our releases_ page.

v0.x.y
------

*Released on 2018-xx-xx*



Breaking Changes
~~~~~~~~~~~~~~~~


Features
~~~~~~~~
- New plugin hook: ``pretalx.submission.signals.submission_state_change`` is triggered on any state change by a submission.
- The frab compatible xml export now has the pretalx version in an xml comment, to remain compatible with frab exports.

Fixed bugs
~~~~~~~~~~~

- Speakers could see their submission in the orga backend, but could access no information they did not put there themselves. (#375)

.. _releases: https://github.com/pretalx/pretalx/releases
