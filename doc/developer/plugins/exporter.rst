.. highlight:: python
   :linenothreshold: 5

Writing an exporter plugin
==========================

An Exporter is a method to export the submission or schedule data in pretalx for later use in another program.

In this document, we will walk through the creation of an exporter output plugin step by step.

Please read :ref:`Creating a plugin <pluginsetup>` first, if you haven't already.

Exporter registration
---------------------

The exporter API does not make a lot of usage from signals, but it does use a
signal to get a list of all available exporters. Your plugin should listen for
this signal and return the subclass of ``pretalx.common.exporter.BaseExporter``
that we'll provide in this plugin::

    from django.dispatch import receiver

    from pretalx.common.signals import register_data_exporters


    @receiver(register_data_exporters, dispatch_uid="exporter_myexporter")
    def register_data_exporter(sender, **kwargs):
        from .exporter import MyExporter
        return MyExporter


The exporter class
------------------

.. class:: pretalx.common.exporter.BaseExporter

   The central object of each exporter is the subclass of ``BaseExporter``.

   .. py:attribute:: BaseExporter.event

   .. autoattribute:: identifier

      This is an abstract attribute, you **must** override this!

   .. autoattribute:: verbose_name

      This is an abstract attribute, you **must** override this!

   .. autoattribute:: public

      This is an abstract attribute, you **must** override this!

   .. automethod:: show_qrcode

   .. automethod:: get_qrcode

   .. automethod:: urls

   .. autoattribute:: icon

      This is an abstract attribute, you **must** override this!

   .. automethod:: render

      This is an abstract method, you **must** override this!

Access
------

The export will now be available for organisers in the schedule related export view.
If you've set ``public = True``, it will also show up in the drop down in the event agenda.
