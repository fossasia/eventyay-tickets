from pretalx.common.signals import EventPluginSignal

register_mail_placeholders = EventPluginSignal()
"""
This signal is sent out to get all known email text placeholders. Receivers should return
an instance of a subclass of pretalx.mail.placeholder.BaseMailTextPlaceholder or a list of these.

As with all event-plugin signals, the ``sender`` keyword argument will contain the event.
"""
