from pretalx.common.signals import EventPluginSignal

register_recording_provider = EventPluginSignal()
"""
This signal is sent out to gather all known recording providers. Receivers
should return a subclass of pretalx.agenda.recording.BaseRecordingProvider.

As with all event plugin signals, the ``sender`` keyword argument will contain
the event.
"""
html_above_session_pages = EventPluginSignal()
"""
This signal is sent out to display additional information on the public session
pages.

As with all plugin signals, the ``sender`` keyword argument will contain the event.
Additionally, the signal will be called with the ``request`` it is processing, and
the ``submission`` which is currently displayed.
The receivers are expected to return HTML.
"""
html_below_session_pages = EventPluginSignal()
"""
This signal is sent out to display additional information on the public session
pages.

As with all plugin signals, the ``sender`` keyword argument will contain the event.
Additionally, the signal will be called with the ``request`` it is processing, and
the ``submission`` which is currently displayed.
The receivers are expected to return HTML.
"""
