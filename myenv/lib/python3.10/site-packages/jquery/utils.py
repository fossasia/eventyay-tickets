from . import __version__
from django.conf import settings
from django.forms import Media

JQUERY_FULL = 'js/jquery.js'
JQUERY_MINIFIED = 'js/jquery.min.js'

if hasattr(settings, 'JQUERY_CDN'):
    jquery_path = settings.JQUERY_CDN.format({
        'version': __version__,
        'min': '' if settings.DEBUG else '.min',
    })
else:
    jquery_path = JQUERY_FULL if settings.DEBUG else JQUERY_MINIFIED

jquery_media_js = (jquery_path, )
jquery_media = Media(js=jquery_media_js)
