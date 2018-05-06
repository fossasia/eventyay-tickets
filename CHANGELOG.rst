Changelog
=========

This changelog contains the changes to be released in the **next** release.
For older changelogs, please visit our releases_ page.

v0.6.0
------

*Released on 2018-05-06*


Breaking Changes
~~~~~~~~~~~~~~~~

None.


Features
~~~~~~~~
- New plugin hook: ``pretalx.submission.signals.submission_state_change`` is triggered on any state change by a submission.
- The frab compatible xml was improved by using correct UUIDs, and includes an XML comment with a pretalx version string.
- The general look and feel and colorscheme has been improved.
- Organisers can make more changes to speaker profiles and submissions to ease event administration.
- pretalx now has a concept of organisers and teams.
- To avoid running into issues when uploading custom CSS, and ensuring smooth operations, custom colors and CSS is not used in the organiser area anymore.
- You can now send mails from templates and use shortcuts from submissions to send mails to specific speakers.
- Since different events have different needs, organisers can now choose if submission abstracts, descriptions, and speaker biographies are required for their event.

Fixed bugs
~~~~~~~~~~~

- Speakers could see their submission in the orga backend, but could access no information they did not put there themselves. (#375)
- The API showed talks to organisers if no schedule had been released yet. It did not show the information to unauthorised users.
- There was no possibility to reset a user's API token.
- If an organiser changed a speaker's email address, they could assign an address already in use in the pretalx instance, resulting in buggy behaviour all around.

.. _releases: https://github.com/pretalx/pretalx/releases
