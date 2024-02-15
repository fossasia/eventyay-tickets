def guess_schedule_version(event):
    if not event.current_schedule:
        return "0.1"

    version = event.current_schedule.version
    prefix = ""
    for separator in [",", ".", "-", "_"]:
        if separator in version:
            prefix, version = version.rsplit(separator, maxsplit=1)
            break
    if version.isdigit():
        version = str(int(version) + 1)
        return prefix + separator + version
    return ""
