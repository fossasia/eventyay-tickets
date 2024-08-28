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
   :members: periodic_task, register_locales, register_data_exporters, register_my_data_exporters

.. automodule:: pretalx.submission.signals
   :members: submission_state_change

.. automodule:: pretalx.schedule.signals
   :members: schedule_release, register_my_data_exporters

.. automodule:: pretalx.mail.signals
   :members: register_mail_placeholders, queuedmail_post_send

Exporters
---------

.. automodule:: pretalx.common.signals
   :no-index:
   :members: register_data_exporters


Organiser area
--------------

.. automodule:: pretalx.orga.signals
   :members: nav_event, nav_global, html_head, activate_event, nav_event_settings, event_copy_data

.. automodule:: pretalx.common.signals
   :no-index:
   :members: activitylog_display, activitylog_object_link

Display
-------

.. automodule:: pretalx.cfp.signals
   :members: cfp_steps, footer_link, html_above_submission_list, html_above_profile_page, html_head

.. automodule:: pretalx.agenda.signals
   :members: register_recording_provider, html_above_session_pages, html_below_session_pages
