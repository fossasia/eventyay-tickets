def is_video_enabled(event):
    """
    Check if the video plugin is enabled
    @param event: event object
    @return: boolean
    """
    if (
        'pretix_venueless' not in event.get_plugins()
        or not event.settings.venueless_url
        or not event.settings.venueless_issuer
        or not event.settings.venueless_audience
        or not event.settings.venueless_secret
    ):
        return False
    return True
