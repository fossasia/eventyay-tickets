from pretalx.common.signals import EventPluginSignal

register_mail_placeholders = EventPluginSignal()
"""
This signal is sent out to get all known email text placeholders. Receivers should return
an instance of a subclass of pretalx.mail.placeholder.BaseMailTextPlaceholder or a list of these.

As with all event-plugin signals, the ``sender`` keyword argument will contain the event.
"""

queuedmail_pre_send = EventPluginSignal()
"""
This signal is sent out before a ``QueuedMail`` will been sent.
Receivers may set the ``sent`` timestamp to skip sending via the regular
email backend. The email text and HTML is rendered after this signal has
been processed, so you can also alter the email’s content here.
Any exceptions raised by receivers will be ignored.

Please note that this signal is only sent for ``QueuedMail`` instances that
are saved/persisted in the database and that belong to an event. This means
that you will not receive this signals for emails like password resets or
draft reminders, or anything else that pretalx thinks should be private
between the sender and the recipient.

As with all event-plugin signals, the ``sender`` keyword argument will
contain the event. Additionally, the ``mail`` keyword argument contains
the ``QueuedMail`` instance itself.
"""

queuedmail_post_send = EventPluginSignal()
"""
This signal is sent out after a ``QueuedMail`` has been sent. Return value
of receivers will be ignored. Receivers must not alter any data of the
``QueuedMail`` instance.

As with all event-plugin signals, the ``sender`` keyword argument will
contain the event. Additionally, the ``mail`` keyword argument contains
the ``QueuedMail`` instance itself.
"""
