from django.dispatch import receiver

from pretalx.common.signals import register_data_exporters


@receiver(register_data_exporters, dispatch_uid="exporter_builtin_ical")
def register_ical_exporter(sender, **kwargs):
    from .exporters import ICalExporter
    return ICalExporter


@receiver(register_data_exporters, dispatch_uid="exporter_builtin_xml")
def register_xml_exporter(sender, **kwargs):
    from .exporters import FrabXmlExporter
    return FrabXmlExporter


@receiver(register_data_exporters, dispatch_uid="exporter_builtin_xcal")
def register_xcal_exporter(sender, **kwargs):
    from .exporters import FrabXCalExporter
    return FrabXCalExporter


@receiver(register_data_exporters, dispatch_uid="exporter_builtin_json")
def register_json_exporter(sender, **kwargs):
    from .exporters import FrabJsonExporter
    return FrabJsonExporter
