from django.conf import settings
from django.forms.widgets import Media
from jquery.utils import jquery_media_js

FORMSET_FULL = 'js/jquery.formset.js'
FORMSET_MINIFIED = 'js/jquery.formset.min.js'

formset_js_path = FORMSET_FULL if settings.DEBUG else FORMSET_MINIFIED

formset_media_js = jquery_media_js + (formset_js_path, )
formset_media = Media(js=formset_media_js)
