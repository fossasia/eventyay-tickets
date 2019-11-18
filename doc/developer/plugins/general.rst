.. highlight:: python
   :linenothreshold: 5

.. _`pluginsignals`:

General APIs
============

This page lists some general signals and hooks which do not belong to a
specific plugin but might come in handy for all sorts of plugin.

Core
----

.. automodule:: pretalx.common.signals
   :members: periodic_task

.. automodule:: pretalx.submission.signals
   :members: submission_state_change

Exporters
---------

.. automodule:: pretalx.common.signals
   :members: register_data_exporters


Organiser area
--------------

.. automodule:: pretalx.orga.signals
   :members: nav_event, nav_global, activate_event, nav_event_settings

Display
-------

.. automodule:: pretalx.cfp.signals
   :members: cfp_steps, footer_link

.. automodule:: pretalx.agenda.signals
   :members: register_recording_providers
