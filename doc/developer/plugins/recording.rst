Writing an recording provider plugin
====================================

A Recording Provider is a way to provide iframes of videos that will be
displayed on the public talk pages of a talk.

In this document, we will walk throug the creation of a plugin for a new
recording provider step by step. If you'd like to look at a completed working
recording provider, take a look at our `plugin for media.ccc.de
<https://github.com/pretalx/pretalx-media-ccc-de>`_.

Please read :ref:`Creating a plugin <pluginsetup>` first, if you haven't
already.

Recording Provider registration
-------------------------------

The recording provider API uses only one signal to collect a list of all
available providers. Your plugin should listen for this signal and return a
subclass of ``pretalx.agenda.recording.BaseRecordingProvider``::

   from django.dispatch import receiver

   from pretalx.agenda.signals import register_recording_provider


   @receiver(register_recording_provider)
   def media_ccc_de_provider(sender, **kwargs):
      from .recording import VimeoProvider
       return VimeoProvider(sender)


The recording provider class
----------------------------

.. class:: pretalx.agenda.recording.BaseRecordingProvider

   The central object of each recording provider is the subclass of ``BaseRecordingProvider``.

   .. py:attribute:: BaseRecordingProvider.event

   .. automethod:: get_recording

      This is an abstract method, you **must** override this!
      The method receives the submission and should return a dictionary
      containing an 'iframe' and a 'csp_header', if a recording iframe
      should be shown.

Hints and considerations
------------------------

There are a couple of things you might want to consider while working on your
recording provider:

Using the ``periodic_task`` :ref:`plugin signal <pluginsignals>` is helpful if
you want to find new recordings automatically – but take care not to do this
overly much. Looking for new recordings once an hour while the event is running
and in the week afterwards should be sufficient.

If you're able to gather recording URLs automatically, your users will still
want an interface to see and potentially edit said recording URLs.
