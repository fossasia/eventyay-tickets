from pretalx.common.signals import EventPluginSignal

register_mail_placeholders = EventPluginSignal()
"""
This signal is sent out to get all known email text placeholders. Receivers should return
an instance of a subclass of pretalx.mail.placeholder.BaseMailTextPlaceholder or a list of these.

As with all event-plugin signals, the ``sender`` keyword argument will contain the event.
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
