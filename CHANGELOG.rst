Changelog
=========

This changelog contains the changes to be released in the **next** release.
For older changelogs, please visit our releases_ page.

vx.x.x
------

*Released on 2017-xx-xx*

Breaking Changes
~~~~~~~~~~~~~~~~

- The default value for email SSL usage is now ``False``, permitting the default
  configuration of ``localhost:25`` to work on more machines out of the box.
- We removed the ``whitenoise`` dependency, meaning that you will have to
  configure static file delivery in your webserver, as we always recommended
  in our documentation.

Features
~~~~~~~~

- E-mails are now sent with a multipart/HTML version, featuring the mail's text
  in a box, styled with the event's primary color. (#159)
- You can now choose to hide the public schedule (including talk pages and
  speaker pages, but excluding feedback pages and the schedule.xml export) (#126)
- Mail template placeholders are now validated so that templates including
  invalid placeholders cannot be saved at all. (#215)
- You can now ask questions that take an uploaded file as an answer. (#208)
- Speakers can now upload files which will be shown on their talk page. (#209)
- The review interface has been rewritten to include fewer pages with more
  information relevant to the user, dependent on event stages and their role
  in the event. (#195, #210)
- pretalx can now be configured to run with celery (an asynchronous task
  scheduler) for long running tasks and tasks like email sending. A new config
  section was added, and usage has been documented. (#38)
- A ``rebuild`` command was introduced that recompiles all static assets.
- Question answers now receive a nice evaluation, aggregating all given answers.
  (#207)
- Questions may now be marked as 'answers contain personal data'. Answers of
  these questions are deleted when users delete their accounts. (#233)
- We moved to a new permission system that allows for more flexible roles.
  Please report any bugs that may relate to incorrect permissions. (#78)
- You can now configure a custom domain to use with your event, in case
  you have an event specific domain for each of your events. (#171)

Fixed bugs
~~~~~~~~~~~

- pretalx crashed when an incorrect invite key was used, now it shows a 404
  page (#304).
- When building absolute URLs for exports, emails, and RSS feeds, 'localhost'
  was used instead of the actual configured URL.
- If an account was configured to be both an orga member and a reviewer, it
  encountered access rights issues.
- When removing the custom orga color, and then adding it again, caching issues
  could be encountered.
- Inactive questions (questions not shown to speakers) could not be edited.
- In some places, gravatar images of the visiting user were shown instead of
  the speaker.
- The event stage display could show several conflicting phases as active.


.. _releases: https://github.com/pretalx/pretalx/releases
