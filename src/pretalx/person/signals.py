from django.dispatch import receiver

from pretalx.common.signals import register_data_exporters


@receiver(register_data_exporters, dispatch_uid="exporter_builtin_csv_speaker")
def register_speaker_csv_exporter(sender, **kwargs):
    from .exporters import CSVSpeakerExporter

    return CSVSpeakerExporter
