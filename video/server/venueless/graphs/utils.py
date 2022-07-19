import logging
from datetime import timedelta

import requests
from pdfrw import PdfReader
from pdfrw.buildxobj import pagexobj
from pdfrw.toreportlab import makerl
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import Flowable

from venueless.core.models import World

logger = logging.getLogger(__name__)


class PdfImage(Flowable):
    def __init__(self, filename_or_object, width=None, height=None, kind="direct"):
        # If using StringIO buffer, set pointer to begining
        if hasattr(filename_or_object, "read"):
            filename_or_object.seek(0)
        page = PdfReader(filename_or_object, decompress=False).pages[0]
        self.xobj = pagexobj(page)
        self.imageWidth = width
        self.imageHeight = height
        x1, y1, x2, y2 = self.xobj.BBox

        self._w, self._h = x2 - x1, y2 - y1
        if not self.imageWidth:
            self.imageWidth = self._w
        if not self.imageHeight:
            self.imageHeight = self._h
        self.__ratio = float(self.imageWidth) / self.imageHeight
        if kind in ["direct", "absolute"] or width is None or height is None:
            self.drawWidth = width or self.imageWidth
            self.drawHeight = height or self.imageHeight
        elif kind in ["bound", "proportional"]:
            factor = min(float(width) / self._w, float(height) / self._h)
            self.drawWidth = self._w * factor
            self.drawHeight = self._h * factor

    def wrap(self, aW, aH):
        return self.drawWidth, self.drawHeight

    def drawOn(self, canv, x, y, _sW=0):
        if _sW > 0 and hasattr(self, "hAlign"):
            a = self.hAlign
            if a in ("CENTER", "CENTRE", TA_CENTER):
                x += 0.5 * _sW
            elif a in ("RIGHT", TA_RIGHT):
                x += _sW
            elif a not in ("LEFT", TA_LEFT):
                raise ValueError("Bad hAlign value " + str(a))

        xobj = self.xobj
        xobj_name = makerl(canv._doc, xobj)

        xscale = self.drawWidth / self._w
        yscale = self.drawHeight / self._h

        x -= xobj.BBox[0] * xscale
        y -= xobj.BBox[1] * yscale

        canv.saveState()
        canv.translate(x, y)
        canv.scale(xscale, yscale)
        canv.doForm(xobj_name)
        canv.restoreState()


def median_value(queryset, term):
    values = [
        v for v in queryset.values_list(term, flat=True).order_by(term) if v is not None
    ]
    count = len(values)
    if not count:
        return timedelta(seconds=0)
    if count % 2 == 1:
        return values[int(round(count / 2))]
    else:
        llim = max(0, int(count / 2 - 1))
        ulim = max(0, int(count / 2 + 1))
        return (
            sum(
                values[llim:ulim],
                start=timedelta(seconds=0),
            )
            / 2
        )


def get_schedule(world: World, fail_silently=True):
    pretalx_config = world.config.get("pretalx", {})
    if pretalx_config.get("url"):
        url = pretalx_config["url"]
    elif pretalx_config.get("domain"):
        domain = pretalx_config.get("domain")
        if not domain.endswith("/"):
            domain += "/"
        url = (
            pretalx_config["domain"]
            + pretalx_config["event"]
            + "/schedule/widget/v2.json"
        )
    else:
        return {}

    try:
        r = requests.get(url)
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        logger.exception(f"Could not load schedule for world {world.pk} from {url}")
        if fail_silently:
            return {}
        else:
            raise


def pretalx_uni18n(i18nstring, locale="en"):
    if not i18nstring:
        return ""
    if isinstance(i18nstring, str):
        return i18nstring
    if i18nstring.get(locale):
        return i18nstring[locale]
    if i18nstring.get("en"):
        return i18nstring["en"]
    return next(i18nstring.values())
