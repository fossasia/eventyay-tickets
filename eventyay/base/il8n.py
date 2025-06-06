
@contextmanager
def language(lng, region=None):
    """
    Temporarily change the active language to ``lng``. Will automatically be rolled back when the
    context manager returns.

    You can optionally pass a "region". For example, if you pass ``en`` as ``lng`` and ``US`` as
    ``region``, the active language will be ``en-us``, which will mostly affect date/time
    formatting. If you pass a ``lng`` that already contains a region, e.g. ``pt-br``, the ``region``
    attribute will be ignored.
    """
    _lng = translation.get_language()
    lng = lng or settings.LANGUAGE_CODE
    if '-' not in lng and region:
        lng += '-' + region.lower()
    translation.activate(lng)
    try:
        yield
    finally:
        translation.activate(_lng)
