from pretalx.common.signals import EventPluginSignal

submission_state_change = EventPluginSignal(
    providing_args=['submission', 'old_state', 'user'],
)
"""
This signal allows you to trigger additional events when a submission changes
its state. You will receive the submission after it has been saved, the previous
state, and the user triggering the change if available.
Any exceptions raised will be ignored.

As with all plugin signals, the ``sender`` keyword argument will contain the event.
"""
