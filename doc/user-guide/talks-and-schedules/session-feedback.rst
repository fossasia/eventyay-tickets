Session feedback
================

.. _`user-guide-session-feedback`:

Attendees can leave comments and optional ratings on scheduled sessions.
Organisers control when feedback opens, who may comment, whether comments are
public, and how moderation works.

This page covers the **session feedback** feature on talk pages. It is separate
from proposal **reviews** (structured scoring during the Call for Papers) and
from video-room prompts in the online event UI.

Overview
--------

When feedback is enabled for an event:

* Attendees (or any registered users, depending on settings) can comment on a
  session's public talk page.
* Comments can include an optional emoji rating (1–5) and can target a specific
  speaker or all speakers on the session.
* Organisers moderate feedback from the Sessions area and can export it as CSV
  or JSON.
* Speakers can read feedback directed at them on a dedicated feedback page.

Feedback is **off by default** for new events.

Organiser perspective
---------------------

Enable and configure feedback
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. Open the event organiser area.
2. Go to **Settings → Feedback**.
3. Enable **Enable feedback for sessions**.
4. Configure the options below, then save.

Disabling feedback later hides comments from the public UI. The settings page
asks for confirmation before you turn the feature off.

Available settings
~~~~~~~~~~~~~~~~~~

=============================== ===========================================================
Setting                         Effect
=============================== ===========================================================
**Enable feedback for sessions** Master switch for session feedback on this event.
**Automatically close comments after** Number of days after the session ends when new
                                comments stop being accepted. ``0`` means never auto-close.
**Who can comment**             **Only attendees** (users with a matching ticket) or
                                **Any registered user**.
**Comments enabled time**       Open comments **after the session is finished**, or as
                                soon as the session is **published** on the agenda.
**Show public feedback on session pages** Display published public comments on the talk page.
**Require public feedback to be reviewed** New public comments start in a review queue
                                until an organiser approves them.
**Anonymous feedback**          **All feedback is public**, **Users can choose**, or
                                **All feedback is anonymous**.
=============================== ===========================================================

“Anonymous” still stores the author for organisers. It only hides the author’s
identity on the public talk page and in the speaker-facing feedback view.

Permissions
^^^^^^^^^^^

* Viewing the event-wide feedback list requires permission to list submissions
  (typically organisers and staff with session access).
* Viewing feedback for a single session requires permission to view that
  session’s feedback (organisers, reviewers, and the session’s speakers, as
  configured by event permissions).
* Moderating (approve, hide, delete, ban) requires permission to update
  submissions.

Where to view feedback
^^^^^^^^^^^^^^^^^^^^^^

**Event-wide list**

1. Open **Sessions → Feedback** in the organiser navigation (visible when
   feedback is enabled).
2. Use the tabs to filter entries:

   * **Published** – visible public comments
   * **Pending** – awaiting review (when review is required)
   * **Hidden** – moderated out of public view
   * **Anonymous** – comments marked non-public

The list is a flat table with a session column. Open a session link to jump to
that session’s feedback.

**Per-session list**

Open a session in the organiser area and use the **Feedback** tab when feedback
exists for that session.

Moderation
^^^^^^^^^^

From the feedback list or the public talk page (for users with update
permission), organisers can:

* Approve pending public comments
* Hide comments
* Soft-delete comments
* Ban or unban users from commenting on the event
* Run bulk approve / hide / delete on pending items

Export
^^^^^^

1. Open the event **Import / Export** settings page.
2. Use the **Feedback** export section.
3. Download **Feedback CSV** or **Feedback JSON**.

Exported fields:

* ``session_title``
* ``session_code``
* ``speaker_name`` (target speaker, if set)
* ``rating``
* ``review`` (comment text)

Exports do **not** currently include author identity, publication status,
anonymity, report counts, or timestamps. Use the organiser UI for moderation
metadata.

Attendee perspective
--------------------

Where to submit feedback
^^^^^^^^^^^^^^^^^^^^^^^^

Open the session’s **public talk page** and scroll to the feedback / comments
section.

There is also a dedicated URL at ``/talk/<code>/feedback/``:

* Non-speakers can submit feedback there (legacy form UI with star ratings).
* Speakers of that session see a read-only list of feedback aimed at them.

The primary path for attendees is the talk page comment composer.

When feedback becomes available
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

All of the following must be true:

1. The organiser has enabled session feedback.
2. The session has a schedule slot.
3. Timing matches the event setting:

   * **After finished** – commenting opens at or after the session end time
     (or start time if no end is set).
   * **After published** – commenting opens once the session is visible on the
     public agenda.
4. If an auto-close window is set, the current time is still within that many
   days after the session ends.
5. You are logged in, not banned from commenting, and allowed by the
   “Who can comment” setting (ticket holder and/or any registered user).

Organisers with submission-update permission can always comment when the period
is open.

What you can submit
^^^^^^^^^^^^^^^^^^^

On the talk page:

* **Comment text** (required in the compose UI; Markdown-style help may be shown)
* **Optional rating** on a 1–5 emoji scale
* **Optional speaker target** – one speaker, or all speakers on the session
  (single-speaker sessions are assigned automatically)
* **Public vs anonymous** – only when the organiser allows a choice

You must be logged in. Even anonymous comments keep an author record for
organisers.

After submitting
^^^^^^^^^^^^^^^^

* You see a success message and return to the talk page.
* If public comments require review, your comment stays **pending** until an
  organiser approves it.
* Otherwise it is **published** immediately (and appears publicly only if
  “Show public feedback” is enabled).

Edit and delete
^^^^^^^^^^^^^^^

* There is **no edit form** after submit.
* You can soft-delete your own comment from the public action menu when
  available.
* You can report other comments; organisers see report counts while moderating.
* You can upvote or downvote comments via the reaction controls when shown.

Functionality checklist
-----------------------

* Enable / disable session feedback per event
* Restrict commenting to ticket holders or all registered users
* Open comments after session end or after agenda publication
* Auto-close comments after a configurable number of days
* Optional public display of published comments
* Optional organiser review queue for public comments
* Public, optional-anonymous, or always-anonymous modes
* Optional 1–5 emoji (or star) rating
* Optional speaker targeting
* Threaded replies
* Reactions (upvote / downvote)
* Report, hide, delete, ban / unban
* Organiser event-wide and per-session feedback lists
* CSV and JSON export of session, speaker, rating, and review text
* Speaker-facing feedback inbox on ``/talk/<code>/feedback/``

Video walkthrough
-----------------

.. note::
   A short screen-recording walkthrough (enable settings → submit as attendee →
   review and export as organiser) will be linked here when published.
   Tracking issue: https://github.com/fossasia/eventyay/issues/5539

Until the recording is available, follow the organiser and attendee steps above.

Limitations and notes
---------------------

* Session feedback is distinct from CfP **proposal reviews**.
* Ticket-gated commenting depends on products configured for admission /
  online access. Misconfigured products can block attendees who expect to
  comment.
* The talk-page composer and the dedicated ``/feedback/`` form use slightly
  different rating UIs (emoji vs stars). Prefer the talk page for attendees.
* Exported files omit author and moderation metadata; use the organiser
  feedback lists for full context.
* Soft-deleted comments remain in the database with status ``deleted`` and are
  not shown in the standard tabs.

Related pages
-------------

* :doc:`sessions` – sessions, proposals, and scheduling
* :doc:`../imports-and-exports/index` – exporters including feedback
* :doc:`../attendee-guide/index` – attendee-facing overview
