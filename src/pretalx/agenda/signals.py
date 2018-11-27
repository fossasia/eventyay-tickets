from pretalx.common.signals import EventPluginSignal

register_recording_provider = EventPluginSignal(providing_args=[])
"""
This signal is sent out to gather all known recording providers. Receivers
should return a subclass of pretalx.agenda.recording.BaseRecordingProvider.

As with all event plugin signals, the ``sender`` keyword argument will contain
the event.
"""
