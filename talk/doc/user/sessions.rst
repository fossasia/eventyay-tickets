.. _`user-guide-proposals`:

Sessions & Proposals
====================

In pretalx, sessions (also called proposals) contain the content of your event
– the talks, workshops, and other programming items that make up your schedule.

.. note::
    We use the word "proposal" typically to mean a session that was submitted, but
    has not (yet) been accepted – but the underlying data structure is the same.

What is not a Session?
----------------------

Not everything that appears in your schedule needs to be a session. Breaks, social events,
and organisational slots (like opening/closing ceremonies) are often better handled as
simple schedule entries rather than full sessions. These items typically don't need their
own detail pages, speaker information, or proposal workflows - they just need to appear
in the right place on the schedule.

For example, a lunch break just needs a time slot and perhaps a location, but doesn't
need a description page or speakers. Similarly, a "Registration Open" slot just needs
to show up in the schedule at the right time. You can learn more about managing these
schedule-only items in the :ref:`Scheduling Guide <user-guide-schedule>`.

Session Lifecycle
-----------------

Sessions go through several states during their lifecycle, and these states and
their transitions are a key part of pretalx.

Submitted
^^^^^^^^^

When a session is first created, it enters the "submitted" state. This happens
either when a speaker submits through the Call for Proposals (CfP) or when an
organiser manually creates the session without selecting a different starting
state. At this point, the session is “just” a proposal.

While a session is in the “submitted” state, the speaker(s) *may* be able to
edit the session, depending on several factors: If the CfP is still open, a
session can be edited, as the speakers otherwise could withdraw and re-submit
their proposal. Once the CfP is closed, the setting of the active review phase
applies, with the default being to prevent edits.

Accepted
^^^^^^^^

Organisers or reviewers will mark sessions that are selected to be part of the
schedule as "accepted", usually in bulk from the review dashboard (see more at
:ref:`Review Guide <user-guide-review>`). This triggers a notification to the
speaker(s) and moves the session into the pool of content available for
scheduling.

.. note::
    When accepting sessions, notification emails are not sent immediately but are
    placed in the outbox for review first. You can learn more about managing
    emails in the :ref:`Email Guide <user-guide-emails>`.

The acceptance notification email is based on the acceptance template, which
organisers can edit before accepting sessions. If you have accepted sessions,
but would like to change the template after the fact, you can discard the
generated email from your outbox, and then use the acceptance email template in
the email composer to send an email to the group of accepted speakers.

Sessions can be scheduled once they are in the "accepted" state (even if they are only in
the “pending accepted” state). However, they will not be visible to the public until they
are in the "confirmed" state – see more in the :ref:`Scheduling Guide <user-guide-schedule>`.

Confirmed
^^^^^^^^^
The acceptance email will contain a link that the speaker can use to confirm
their attendance.

.. note::
    If you wish to skip this step, you can mark proposals as confirmed
    directly, rather than as accepted first. Organisers can always change
    the state of a session manually.

Confirmed sessions will be visible to the public on the schedule, though
pretalx makes sure to not change the schedule without the organiser’s input:
You will need to release a new schedule version to make the changes visible to
the public, and you will see which sessions will become publicly visible. See
more in the :ref:`Scheduling Guide <user-guide-schedule>`.

Rejected
^^^^^^^^

Sessions that are not selected for the event are marked as "rejected", and an
email is generated like for accepted proposals, using the rejection email template.
Rejected sessions are kept in the system for record-keeping, but can no longer be edited
by the submitter/speaker.

Withdrawn
^^^^^^^^^

Speakers may choose to withdraw their session. They can only do so while the session
is in the “submitted” state and still editable. Otherwise, speakers are asked to
contact the organisers to withdraw their session, so that proposals or sessions
can’t be removed from the event unilaterally.


.. _`user-guide-proposals-pending`:

Pending States
^^^^^^^^^^^^^^

When you change a proposal’s state, you can choose to set the new state as “pending”.
If you do this, the proposal will keep its current state, while gaining a new pending
state – this means that the public state of the proposal (e.g. what the submitter/speaker
or the public see) is not affected, but organisers and reviewers will see both
the current and the pending states.

This is particularly useful for accepting and rejecting sessions, where you often want
to make the decisions in advance and step-by-step, but only want speakers to be notified
of your decisions at a specific time, and all at once.

If you have any pending states, you will see a notification in the dashboard, and you can
click on it or on the button at the top of your session list to apply all pending states
(i.e. to turn the pending states into the current states). If you only want to apply some
of the pending states, you can filter the session list to show only the sessions you
want to change, and then apply the pending states to only those sessions by clicking the
button at the top of the list.

Organisation Features
---------------------

Sessions have several features that help organisers manage and categorise them:

.. _`user-guide-tracks`:

Tracks
^^^^^^

Tracks are thematic groupings of sessions. For example, you might have tracks for "Security", "Web Development", and "Career Development".
You can assign colours to tracks, in order to make them distinct in the public schedule, so that attendees can see at a glance which sessions belong together.

Tracks can also be used to assign reviewer permissions, which is useful if your reviewers are domain experts in specific topics (more in the :ref:`Review Guide <user-guide-review>`).

You don’t have to use tracks at all, and you can turn them off in the CfP settings.

Session Types
^^^^^^^^^^^^^

Session Types define the format and default duration of sessions. Common examples include:

- Long talk (45 minutes)
- Short talk (20 minutes)
- Workshop (2 hours)
- Lightning talk (5 minutes)

Session types make scheduling easier for you, because you can just drag blocks of the correct duration onto the schedule.
You can always override the duration of a session individually, but offering these categories can help the submitter communicate their intended format from the beginning.

If you don’t want to use session types, just don’t create any beyond the default one that pretalx creates for you.
If there is only a single session type, pretalx will not show the session type selection field at all.

Tags
^^^^

Tags are internal labels that help organisers categorise and filter sessions.
Only organisers and reviewers can see tags, they will not appear on the public schedule.

You can use them for any organisational purpose that comes to mind, from state
markers like “needs work”, organisational notes like “requires mentor”, or
thematic labels like “beginner-friendly”.

We hope to make allow tags to show up in the public schedule in the future, but
any tags existing prior to that point will remain internal.

Speakers
--------

Sessions can have any number of speakers (including none).
If a session is submitted through the CfP, the submitting user is automatically added as a speaker.

Organisers can add or remove speakers at any time.
You can do so from the „Speakers“ tab on the session detail page.
If you add a new speaker to a session, they will receive an email notification.
The notification will be based on the email template „Add a speaker to a proposal (existing account)“ if the email address is already known to pretalx, and on the template „Add a speaker to a proposal (new account)“ if the email address is not yet known.
If the speaker does not have an account yet, their email will contain a link where they can set their account password.

Interaction & Communication
---------------------------

There are two main ways to discuss sessions:

Comments
^^^^^^^^

Anyone with access to the session (organisers and reviewers) can leave comments.
Comments are intended for discussions about the session, useful for clarifying details or suggesting changes.
Because they are timestamped, comments are also useful to note discussions you had with the team or the speaker(s) about the session.

You can think of the comments tab of the session page as a forum page, where you can post multiple times, respond to the comments of others, and read all comments ordered by time.

Reviews
^^^^^^^

Reviews are part of the formal review process and are separate from comments.
They typically contain scores and structured feedback used to evaluate proposals for acceptance – but the details can be configured on a per-event basis.
You can learn more about the review process in the :ref:`Review Guide <user-guide-review>`.

The key differences between comments and reviews are:

- Comments are free-form and can be posted by anyone with access to the session; reviews are structured and can only be posted by users with the review permission.
- Comments can be read by anybody with access to the session; reviews can **never be seen by the speakers of the session**, even if they have review permissions.
- Comments are displayed in order of posting time and anybody can post multiple comments; reviews are displayed in a structured format and only one review per reviewer is allowed.
