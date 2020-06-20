import io
import logging
from collections import Counter, defaultdict
from datetime import timedelta
from os.path import dirname
from urllib.parse import urljoin

import dateutil.parser
import pytz
from django.core.exceptions import PermissionDenied
from django.db.models import Max, Min, Q, Sum
from django.db.models.functions import TruncMinute
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property
from django.utils.timezone import is_naive
from django.views import View
from matplotlib import cbook, dates, pyplot
from matplotlib.figure import Figure

from venueless.core.models import World
from venueless.core.permissions import Permission

logger = logging.getLogger(__name__)

EMOJIS = {
    "clap": urljoin(dirname(__file__) + "/", "data/clap.png"),
    "+1": urljoin(dirname(__file__) + "/", "data/plus1.png"),
    "heart": urljoin(dirname(__file__) + "/", "data/heart.png"),
    "open_mouth": urljoin(dirname(__file__) + "/", "data/open_mouth.png"),
}


class GraphView(View):
    size = (12, 6)
    mimes = {
        "png": "image/png",
        "pdf": "application/pdf",
        "svg": "image/svg+xml",
    }

    @cached_property
    def world(self):
        return get_object_or_404(World, domain=self.request.headers["Host"])

    @cached_property
    def fig(self):
        return Figure(
            figsize=self.size
        )  # Do not enable tight_layout, it breaks emoji markers

    def get(self, request, *args, **kwargs):
        try:
            token = self.world.decode_token(request.GET.get("token"))
            if not token:
                raise PermissionDenied("Invalid token.")
        except:
            raise PermissionDenied("Invalid token.")
        if not self.world.has_permission_implicit(
            traits=token.get("traits"), permissions=[Permission.WORLD_GRAPHS]
        ):
            raise PermissionDenied("Permission denied.")

        self.build()

        t = kwargs["type"]
        buf = io.BytesIO()
        self.fig.savefig(buf, format=t)
        buf.seek(0)
        r = HttpResponse(buf.read(), content_type=self.mimes[t])
        r["Content-Disposition"] = "inline"
        return r

    def build(self):
        raise NotImplementedError()


class RoomAttendanceGraphView(GraphView):
    @cached_property
    def room(self):
        return get_object_or_404(self.world.rooms, pk=self.request.GET.get("room"))

    def build(self):
        gs = self.fig.add_gridspec(1, 1)
        ax = self.fig.add_subplot(gs[0, 0])
        tz = pytz.timezone(self.world.timezone)

        begin = self.room.views.aggregate(min=Min("start"))["min"]
        end = self.room.views.aggregate(max=Max("end"))["max"]

        if "begin" in self.request.GET:
            try:
                begin = dateutil.parser.parse(self.request.GET.get("begin"))
            except ValueError:
                pass

        if "end" in self.request.GET:
            try:
                end = dateutil.parser.parse(self.request.GET.get("end"))
            except ValueError:
                pass

        if is_naive(begin):
            begin = tz.localize(begin)
        if is_naive(end):
            end = tz.localize(end)

        views = (
            self.room.views.filter(
                Q(Q(end__isnull=True) | Q(end__gte=begin)) & Q(start__lte=end)
            )
            .order_by()
            .values("user", "start", "end")
        )

        adds = defaultdict(set)
        for v in views:
            bucket = v["start"].replace(
                second=0, microsecond=0, minute=v["start"].minute // 10 * 10
            )
            while bucket < end and (not v["end"] or bucket < v["end"]):
                adds[bucket].add(v["user"])
                bucket += timedelta(minutes=10)

        pairs = sorted(adds.items())
        keys = [p[0] for p in pairs]
        values = [len(p[1]) for p in pairs]
        ax.plot(keys, values)

        ax.xaxis.set_major_formatter(dates.DateFormatter("%d. %H:%M", tz=tz))
        ax.set_xlim(begin, end)
        ax.set_ylim(0, max(values) * 1.1)
        ax.grid(True)

        reactions = (
            self.room.reactions.filter(datetime__gte=begin, datetime__lte=end,)
            .annotate(min=TruncMinute("datetime"))
            .order_by()
            .values("datetime", "reaction")
            .annotate(amount=Sum("amount"))
        )

        reacts = Counter()
        for r in reactions:
            bucket = r["datetime"].replace(
                second=0, microsecond=0, minute=r["datetime"].minute // 10 * 10
            )
            reacts[bucket, r["reaction"]] += 1

        ax.set_ylabel("Unique viewers")
        ax2 = ax.twinx()
        ax2.set_ylim(0, max(reacts.values()) * 1.4)
        ax2.set_xlim(begin, end)
        ax2.set_ylabel("Emoji reactions")

        for r, emoji in EMOJIS.items():
            pairs = sorted(reacts.items())
            keys = [p[0][0] for p in pairs if p[0][1] == r]
            values = [p[1] for p in pairs if p[0][1] == r]

            emoji_img = pyplot.imread(cbook.get_sample_data(emoji))
            fig_box = self.fig.get_window_extent()
            emoji_size = 0.03
            emoji_axs = [None for i in range(len(keys))]
            for i in range(len(keys)):
                loc = ax2.transData.transform((dates.date2num(keys[i]), values[i]))
                emoji_axs[i] = self.fig.add_axes(
                    [
                        loc[0] / fig_box.width - emoji_size / 2,
                        loc[1] / fig_box.height - emoji_size / 2,
                        emoji_size,
                        emoji_size,
                    ],
                    anchor="C",
                )
                emoji_axs[i].imshow(emoji_img)
                emoji_axs[i].axis("off")
        ax.set_title(self.room.name)
        self.fig.autofmt_xdate()
