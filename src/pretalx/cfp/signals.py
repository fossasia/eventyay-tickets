from pretalx.common.signals import EventPluginSignal

footer_link = EventPluginSignal(
    providing_args=["request"]
)
"""
This signal allows you to add links to the footer of an event page. You are
expected to return a dictionary containing the keys ``label`` and ``url``.

As with all plugin signals, the ``sender`` keyword argument will contain the event.
"""

cfp_steps = EventPluginSignal(
    providing_args=["request"]
)
"""
This signal allows you to add CfP steps of your own. This signal will expect a
list of ``pretalx.cfp.flow.BaseCfPStep`` objects. The integration of CfP steps
in the CfP workflow is currently considered **unstable** and may change without
notice between versions.
"""
