from pretalx.common.signals import EventPluginSignal

footer_link = EventPluginSignal(providing_args=["request"])
"""
This signal allows you to add links to the footer of an event page. You are
expected to return a dictionary containing the keys ``label`` and ``url``.

As with all plugin signals, the ``sender`` keyword argument will contain the event.
"""

cfp_steps = EventPluginSignal(providing_args=["request"])
"""
This signal allows you to add CfP steps of your own. This signal will expect a
list of ``pretalx.cfp.flow.BaseCfPStep`` objects. The integration of CfP steps
in the CfP workflow is currently considered **unstable** and may change without
notice between versions.
"""

html_above_submission_list = EventPluginSignal(providing_args=["request"])
"""
This signal is sent out to display additional information on the personal user
submission list page, above the submission list.

As with all plugin signals, the ``sender`` keyword argument will contain the event. The
receivers are expected to return HTML.
"""

html_above_profile_page = EventPluginSignal(providing_args=["request"])
"""
This signal is sent out to display additional information on the personal user
profile page, above the submission list.

As with all plugin signals, the ``sender`` keyword argument will contain the event. The
receivers are expected to return HTML.
"""
html_head = EventPluginSignal(providing_args=["request"])
"""
This signal allows you to put code inside the HTML ``<head>`` tag of every page
in the frontend (i.e. everything not in the organiser backend). You will get the request
as the keyword argument ``request`` and are expected to return plain HTML.

As with all plugin signals, the ``sender`` keyword argument will contain the event. The
receivers are expected to return HTML.
"""
