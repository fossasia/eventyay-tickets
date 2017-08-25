Features
========

This page aims to give an overview over the already implemented pretalx features, as well as
upcoming or planned features. If you have any further suggestions, please open an issue_ –
neither of these lists are complete, and we're looking forward to what you come up with!

Features
--------

While pretalx is still unfinished, it already comes with a wide range of features. Once our
documentation is more complete, we will introduce user guides for these features, but for
now their descriptions will have to suffice.

Talk submission
~~~~~~~~~~~~~~~

- **Publish a Call for Papers:** This is, at first, the most important part. pretalx allows you
  to publish a beautiful (we support full *markdown*) CfP in *multiple languages* and make it
  public after inspecting it.
- **Build a great team:** Pretalx allows you to invite further members to your crew seamlessly,
  and has already parts of a role-based permission system, where you differentiate between
  superusers, crew, reviewers, etc.
- **Organize the talks:** You can offer multiple submission types, with default lengths, so that
  speakers can tell you how much time (or which format, e.g. workshops) they require right at the
  start.
- **Work with multi-language events:** pretalx allows you to choose the locales offered at your
  conference, and speakers can then choose the language they feel most comfortable in for their
  talk. Subsequently, all emails sent to speakers will be in that language.
- **Ask custom questions:** If you need custom, additional information from your submitters,
  you can add questions to your CfP. We support a wide variety of answer types, such as free-text,
  number input, and multiple choice. (Answers can be optional, too.)
- **Set a deadline:** You can configure a deadline for your CfP and choose to show the countdown
  publicly.
- **Accept or reject submissions:** After careful consideration, you can accept or reject
  submissions. Speakers will then be notified (if you choose to), and asked to confirm their
  talk.

Scheduling
~~~~~~~~~~

- **Configure your location:** Configure the rooms your talks will be held in, including their
  names, descriptions, and capacities.
- **Build a schedule:** In the interactive drag'n'drop interface, build a schedule that you
  are happy with. Play around with it freely.
- **Build your schedule offline:** The initial version of a schedule is often hard to figure
  out. You can print out proportionally sized cards of the talks to cut out and play around with.
- **Publish your schedule:** Whenever something has changed noticably, publish a new schedule
  just by naming it and clicking a button. Speakers will be notified if their talks have been
  moved by the new release.
- **Transparent updates:** pretalx provides a public changelog and an Atom feed, so that your
  participants can be notified as soon as a new schedule version has been released.

Speaker management
~~~~~~~~~~~~~~~~~~

- **Communicate:** Write emails to your speakers! pretalx comes with an email templating system
  that allows you to write multi-lingual email templates with placeholders and send them to
  all or a subset of your speakers.
- **Check, then check again:** pretalx lets you check and edit any email before it is actually
  sent. Until then, the emails are collected in an Outbox, ready for editing, sending, or
  discarding.
- **Resend:** Sent the email to the wrong address? Want to send the same email to an additional
  speaker? pretalx allows you to copy any sent email to a draft, edit it, and send it again.

Features being implemented
--------------------------

- **Reviewing:** A fancy reviewing system with configurable scales, average scores, and maybe
  later on vetos in either direction.

Planned features
----------------

- More detailed permissions system: Crew and superusers were sufficient for the beginning, but
  now there needs to be clear separation between crew and reviewers, and maybe even track based
  reviewer teams. (`issue 78`_)
- Restrict room availability to configurable times (`issue 80`_)
- Offer 'anywhere in the world' deadline timing. (`issue 81`_)
- Warn when scheduling a speaker in multiple talks at the same time. (`issue 46`_)
- Offline schedule display, that saves a version of the schedule page in the browser cache
  and displays it (with a warning) when the user is offline (`issue 15`_)
- Allow questions per speaker, and not only per submission (`issue 42`_)
- Allow speakers to upload profile pictures (and possibly other files) (`issue 44`_)
- Provide an ICAL export (`issue 67`_)
- Allow speakers to submit their availability (`issue 79`_)

.. _issue 15: https://github.com/openeventstack/pretalx/issues/15
.. _issue 42: https://github.com/openeventstack/pretalx/issues/42
.. _issue 44: https://github.com/openeventstack/pretalx/issues/44
.. _issue 46: https://github.com/openeventstack/pretalx/issues/46
.. _issue 67: https://github.com/openeventstack/pretalx/issues/67
.. _issue 78: https://github.com/openeventstack/pretalx/issues/78
.. _issue 79: https://github.com/openeventstack/pretalx/issues/79
.. _issue 80: https://github.com/openeventstack/pretalx/issues/80
.. _issue 81: https://github.com/openeventstack/pretalx/issues/81
