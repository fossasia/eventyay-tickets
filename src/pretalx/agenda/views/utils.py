from pretalx.common.signals import register_data_exporters


def get_schedule_exporters(request):
    exporters = [
        exporter(request.event)
        for _, exporter in register_data_exporters.send(request.event)
    ]
    result = []
    for exporter in exporters:
        if hasattr(exporter, "is_public"):
            try:
                response = exporter.is_public(request=request)
                if response:
                    result.append(exporter)
            except Exception:
                pass
        elif exporter.public or request.is_orga:
            result.append(exporter)
    return result


def find_schedule_exporter(request, name):
    for exporter in get_schedule_exporters(request):
        if exporter.identifier == name:
            return exporter
    return None
