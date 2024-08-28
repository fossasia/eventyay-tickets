from django.dispatch import receiver

from pretalx.common.signals import (
    EventPluginSignal,
    register_data_exporters,
    register_my_data_exporters,
)

schedule_release = EventPluginSignal()
"""
This signal allows you to trigger additional events when a new schedule
version is released. You will receive the new schedule and the user triggering
the change (if any).
Any exceptions raised will be ignored.

As with all plugin signals, the ``sender`` keyword argument will contain the event.
Additionally, you will receive the keyword arguments ``schedule``
and ``user`` (which may be ``None``).
"""


@receiver(register_data_exporters, dispatch_uid="exporter_builtin_ical")
def register_ical_exporter(sender, **kwargs):
    from pretalx.schedule.exporters import ICalExporter

    return ICalExporter


@receiver(register_my_data_exporters, dispatch_uid="exporter_builtin_my_ical")
def register_my_ical_exporter(sender, **kwargs):
    from .exporters import MyICalExporter

    return MyICalExporter


@receiver(register_data_exporters, dispatch_uid="exporter_builtin_xml")
def register_xml_exporter(sender, **kwargs):
    from pretalx.schedule.exporters import FrabXmlExporter

    return FrabXmlExporter


@receiver(register_my_data_exporters, dispatch_uid="exporter_builtin_my_xml")
def register_my_xml_exporter(sender, **kwargs):
    from .exporters import MyFrabXmlExporter

    return MyFrabXmlExporter


@receiver(register_data_exporters, dispatch_uid="exporter_builtin_xcal")
def register_xcal_exporter(sender, **kwargs):
    from pretalx.schedule.exporters import FrabXCalExporter

    return FrabXCalExporter


@receiver(register_my_data_exporters, dispatch_uid="exporter_builtin_my_xcal")
def register_my_xcal_exporter(sender, **kwargs):
    from .exporters import MyFrabXCalExporter

    return MyFrabXCalExporter


@receiver(register_data_exporters, dispatch_uid="exporter_builtin_json")
def register_json_exporter(sender, **kwargs):
    from pretalx.schedule.exporters import FrabJsonExporter

    return FrabJsonExporter


@receiver(register_my_data_exporters, dispatch_uid="exporter_builtin_my_json")
def register_my_json_exporter(sender, **kwargs):
    from .exporters import MyFrabJsonExporter

    return MyFrabJsonExporter
