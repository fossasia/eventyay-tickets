.. _`user-faq`:

FAQ
===

This document collects issues that came up in the past, and that cannot be
solved in pretalx with a reasonable amount of effort or time.

Sessions
--------

What is the difference between tracks and session types?
    Tracks are a way to group sessions by topic, and will be shown in the
    schedule as colour-coded blocks. Session types are a way to determine
    the format and default duration of a session. See more in the
    :ref:`Session user guide <user-guide-tracks>`.

What is the difference between the “accepted” and “confirmed” session status?
    The “accepted” status is used to indicate that a session has been
    accepted by the program committee. The “confirmed” status is used to
    indicate that the speaker has confirmed their participation in the
    conference. The “confirmed” status is set by the speaker, though organisers
    can also set it manually. See more in the :ref:`Session user guide <user-guide-sessions>`.

How do I designate sessions as fallback/alternates?
    To designate sessions as fallback or alternates, you can use the **pending states** feature.
    To do so, leave the session in the “submitted” state, but set it to “pending accepted”.
    Pending states are not shown to speakers, but you can write an email to all speakers with
    proposals marked as “pending accepted” if you want to communicate this decision.
    For more details on how to manage session states, see the
    :ref:`Session Lifecycle <user-guide-proposals-pending>` section in the
    :ref:`Sessions & Proposals <user-guide-proposals>` guide.


Schedule
--------

How can I export my schedule to PDF / print my schedule?
    pretalx does not currently offer a PDF export of the schedule, because of the level of complexity
    that comes with printing a schedule with an arbitrary amount of rooms.
    However, the schedule editor page has print support, hiding the usual pretalx UI elements like the
    menu sidebar. Combined with the schedule editor’s support for hiding rooms, this is the best PDF
    version of the schedule pretalx offers. To use it, navigate to your schedule editor, select your
    browser’s print dialogue, and then select “Print to PDF”.


Email
-----

We run into issues when using Gmail.
    In Google’s eyes, pretalx is a `less secure app`_, which you’ll have to
    grant special access. Even then, Gmail is known to unexpectedly block your
    SMTP connection with unhelpful error messages if you use it to send out too
    many emails in bulk (e.g. all rejections for a conference) even on GSuite,
    so using Gmail for transactional email is a bad idea.


Integrations
------------

How do we create speaker tickets with pretix?
    As there is no direct integration between pretix and pretalx yet (some details
    here `on GitHub`_), the best way to send pretix vouchers to all your pretalx
    speakers is to use the pretalx CSV export.
    Select all accepted and confirmed speakers, and export the name and email
    field. You can then use the bulk voucher form in pretix with the exported
    CSV file directly – you can find more information on the bulk voucher
    sending workflow in the `pretix documentation`_.


.. _less secure app: https://support.google.com/accounts/answer/6010255
.. _on GitHub: https://github.com/pretalx/pretalx/discussions/2027#discussioncomment-13145751
.. _pretix documentation: https://docs.pretix.eu/guides/vouchers/#sending-out-vouchers-via-email
