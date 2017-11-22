Features
========

This page aims to give an overview over the already implemented pretalx features, as well as
upcoming or planned features. If you have any further suggestions, please open an issue_ – neither
of these lists are complete, and we're looking forward to what you come up with!

Features
--------

While pretalx is still unfinished, it already comes with a wide range of features. Once our
documentation is more complete, we will introduce user guides for these features, but for now their
descriptions will have to suffice.

Talk submission
~~~~~~~~~~~~~~~

- **Publish a Call for Papers:** This is, at first, the most important part. pretalx allows you to
  publish a beautiful (we support full *markdown*) CfP in *different languages* and make it public
  after inspecting it.
- **Build a great team:** pretalx allows you to invite further members to your crew seamlessly, and
  has already parts of a role-based permission system, where you differentiate between superusers,
  crew, reviewers, etc.
- **Organize the talks:** You can offer different submission types, with default lengths, so that
  speakers can tell you how much time (or which format, e.g. workshops) they require right at the
  start.
- **Work with multi-language events:** pretalx allows you to choose the locales offered at your
  conference, and speakers can then choose the language they feel most comfortable in for their
  talk. Subsequently, speakers will receive all emails in that language.
- **Ask custom questions:** If you need custom information from your submitters, you can add
  questions to your CfP. We support a wide variety of answer types, such as free-text, number input,
  and choices. (Answers can be optional, too.) You'll see the results as easily manageable
  statistics.
- **Set a deadline:** You can configure a deadline for your CfP and choose to show the countdown
  publicly.
- **Accept or reject submissions:** After careful consideration, you can accept or reject
  submissions. Speakers will then receive a notification (if you choose to), and asked to confirm
  their talk.
- **Reviewing:** A reviewing system with both texts and scoring, configurable scales, average
  scores, and reviewer teams that can work separately from the general orga team.
- **Strong opinions:** Permit reviewers to issue vetos or to force a submission to be accepted, for
  a fixed amount of times per event.

Scheduling
~~~~~~~~~~

- **Configure your location:** Configure the rooms your talks will be taking place in, including
  their names, descriptions, capacities and availabilites.
- **Build a schedule:** In the interactive drag'n'drop interface, build a schedule that you are
  happy with. Play around with it freely.
- **Build your schedule offline:** The initial version of a schedule is often hard to figure out.
  You can print out proportionally sized cards of the talks to cut out and play around with.
- **Publish your schedule:** Whenever something has changed noticeably, publish a new schedule by
  naming it and clicking a button. Speakers will receive notifications if the new release changes
  their talk.
- **Interface:** You can export your schedule in machine readable format (a JSON, XML, or XCAL),
  and use it elsewhere or even import it in other pretalx instances.
- **Transparent updates:** pretalx provides a public changelog and an Atom feed, so that your
  participants can receive notifications as soon as you release a new schedule version.
- **Integrate recordings:** Unless the speakers have set the do-not-record flag, you may sync and
  integrate the recording in the talk's page for the participants' convenience.
- **Provide feedback:** If the speakers wish, they can receive anonymous feedback.

Speaker management
~~~~~~~~~~~~~~~~~~

- **Communicate:** Write emails to your speakers! pretalx comes with an email templating system that
  allows you to write multi-lingual email templates with placeholders and send them to all or a
  subset of your speakers.
- **Check, then check again:** pretalx lets you check and edit any email before it's actually sent.
  Until then, pretalx collects the emails in an Outbox, ready for editing, sending, or discarding.
- **Resend:** Sent the email to the wrong address? Want to send the same email to a new speaker?
  pretalx allows you to copy any sent email to a draft, edit it, and send it again.
- **Educate:** Speakers can upload files (such as presentations, or papers) along with their talks.

Customization
~~~~~~~~~~~~~

- **Comunicate:** Change the default mail templates to something that fits your event and says
  precisely what you want it to say.
- **Colorize:** Change your event's primary color to fit your event, your design, or your organizer.
- **Customize:** If changing the site's primary color is not adequate for you, you can also upload
  custom CSS files and change anything you want to look differently.
- **Link:** You can configure a separate domain for each of your events, in case you have event-
  specific domains, but want to keep all your events on the same instance.

Features under development
--------------------------

- **Tracks:** Introduce a concept of tracks that brings track colors, and track-bound review teams.
- **Automate:** Use our REST API to automate anything related to your conference.

Planned features
----------------

- More detailed permissions system: Crew and superusers were enough for the beginning, but now there
  needs to be clear separation between crew and reviewers, and even track based reviewer teams.
  (`#78 <https://github.com/pretalx/pretalx/issues/78>`_)
- Offer 'anywhere in the world' deadline timing. (`#81
  <https://github.com/pretalx/pretalx/issues/81>`_)
- Warn when scheduling a speaker in more than one talk at the same time. (`#46
  <https://github.com/pretalx/pretalx/issues/46>`_)
- Offline schedule display, that saves a version of the schedule page in the browser cache and
  displays it (with a warning) when the user is offline (`#15
  <https://github.com/pretalx/pretalx/issues/15>`_)
- Allow speakers to submit their availability (`#79
  <https://github.com/pretalx/pretalx/issues/79>`_)

.. _issue: https://github.com/pretalx/pretalx/issues/
