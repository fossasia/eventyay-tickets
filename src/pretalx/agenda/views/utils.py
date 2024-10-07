from contextlib import suppress

from pretalx.common.signals import register_data_exporters


def is_visible(exporter, request, public=False):
    if not public:
        return request.user.has_perm("orga.view_schedule", request.event)
    if not request.user.has_perm("agenda.view_schedule", request.event):
        return False
    if hasattr(exporter, "is_public"):
        with suppress(Exception):
            return exporter.is_public(request=request)
    return exporter.public


def get_schedule_exporters(request, public=False):
    exporters = [
        exporter(request.event)
        for _, exporter in register_data_exporters.send_robust(request.event)
    ]
    return [
        exporter
        for exporter in exporters
        if (
            not isinstance(exporter, Exception)
            and is_visible(exporter, request, public=public)
        )
    ]


def find_schedule_exporter(request, name, public=False):
    for exporter in get_schedule_exporters(request, public=public):
        if exporter.identifier == name:
            return exporter
    return None
