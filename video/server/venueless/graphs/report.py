import io
import tempfile
from datetime import timedelta

import dateutil.parser
import pytz
from django.core.files.base import ContentFile
from django.db import models
from django.db.models import (
    Avg,
    Count,
    ExpressionWrapper,
    F,
    Max,
    Min,
    OuterRef,
    Q,
    Subquery,
    Sum,
)
from django.db.models.functions import Greatest
from django.utils.formats import date_format
from django.utils.functional import cached_property
from django.utils.timezone import is_naive, make_aware, now
from django.utils.translation import ugettext as _
from matplotlib.figure import Figure
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Table,
    TableStyle,
)

from venueless.core.models import Channel, ChatEvent, Room, User
from venueless.core.models.exhibitor import ContactRequest, ExhibitorView
from venueless.core.models.room import RoomView
from venueless.graphs.utils import PdfImage, median_value
from venueless.graphs.views import build_room_view_fig
from venueless.storage.models import StoredFile


class ReportGenerator:
    def __init__(self, world, pdf_graphs=True):
        self.world = world
        self.pdf_graphs = pdf_graphs

    def build(self, input):
        self.input = input

        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            doc = self.get_doc_template()(
                f.name,
                pagesize=self.pagesize,
                leftMargin=15 * mm,
                rightMargin=15 * mm,
                topMargin=20 * mm,
                bottomMargin=15 * mm,
            )
            doc.addPageTemplates(
                [
                    PageTemplate(
                        id="All",
                        frames=self.get_frames(doc),
                        onPage=self.on_page,
                        pagesize=self.pagesize,
                    )
                ]
            )
            doc.build(self.get_story())
            f.seek(0)
            sf = StoredFile.objects.create(
                world=self.world,
                date=now(),
                expires=now() + timedelta(hours=2),
                filename="report.pdf",
                type="application/pdf",
                public=True,
                user=None,
            )
            sf.file.save("report.pdf", ContentFile(f.read()))
            return sf

    @property
    def pagesize(self):
        from reportlab.lib import pagesizes

        return pagesizes.portrait(pagesizes.A4)

    def get_doc_template(self):
        from reportlab.platypus import BaseDocTemplate

        return BaseDocTemplate

    def get_frames(self, doc):
        from reportlab.platypus import Frame

        self.frame = Frame(
            doc.leftMargin,
            doc.bottomMargin,
            doc.width,
            doc.height,
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
            id="normal",
        )
        return [self.frame]

    @cached_property
    def stylesheet(self):
        from reportlab.lib.styles import getSampleStyleSheet

        style = getSampleStyleSheet()
        return style

    def on_page(self, canvas, doc):
        canvas.saveState()
        self.page_footer(canvas, doc)
        self.page_header(canvas, doc)
        canvas.restoreState()

    def page_footer(self, canvas, doc):
        from reportlab.lib.units import mm

        canvas.setFont("Helvetica", 8)
        # canvas.drawString(15 * mm, 10 * mm, _("Page %d") % (doc.page,))
        canvas.drawRightString(
            self.pagesize[0] - 15 * mm,
            10 * mm,
            now().astimezone(self.tz).strftime("%d.%m.%Y %H:%M:%S"),
        )

    def get_right_header_string(self):
        return "venueless"

    def get_left_header_string(self):
        return self.world.title

    def page_header(self, canvas, doc):
        from reportlab.lib.units import mm

        canvas.setFont("Helvetica", 10)
        canvas.drawString(
            15 * mm, self.pagesize[1] - 15 * mm, self.get_left_header_string()
        )
        canvas.drawRightString(
            self.pagesize[0] - 15 * mm,
            self.pagesize[1] - 15 * mm,
            self.get_right_header_string(),
        )
        canvas.setStrokeColorRGB(0, 0, 0)
        canvas.line(
            15 * mm,
            self.pagesize[1] - 17 * mm,
            self.pagesize[0] - 15 * mm,
            self.pagesize[1] - 17 * mm,
        )

    @cached_property
    def tz(self):
        return pytz.timezone(self.world.timezone)

    @cached_property
    def date_begin(self):
        begin = RoomView.objects.filter(room__world=self.world).aggregate(
            min=Min("start")
        )["min"]

        if "begin" in self.input:
            try:
                begin = dateutil.parser.parse(self.input.get("begin"))
                if is_naive(begin):
                    make_aware(begin, self.tz)
            except ValueError:
                pass
        return begin.astimezone(self.tz)

    @cached_property
    def date_end(self):
        end = RoomView.objects.filter(room__world=self.world).aggregate(
            max=Greatest(Max("start"), Max("end"))
        )["max"]

        if "end" in self.input:
            try:
                end = dateutil.parser.parse(self.input.get("end"))
                if is_naive(end):
                    make_aware(end, self.tz)
            except ValueError:
                pass
        return end.astimezone(self.tz)

    def get_story(self):
        s = [
            Paragraph(self.world.title, self.stylesheet["Heading1"]),
        ]
        s += self.global_sums()
        s += self.story_for_exhibitors()

        for room in self.world.rooms.all():
            types = [m["type"] for m in room.module_config]
            if any(
                t.startswith("livestream.")
                or t.startswith("chat.")
                or t.startswith("call.")
                for t in types
            ):
                s += self.story_for_room(room)

        return s

    @cached_property
    def day_whitelist(self):
        # currently not in use
        if "days" not in self.input:
            return None
        return [dateutil.parser.parse(d).date() for d in self.input.get("days")]

    def story_for_room(self, room: Room):
        s = [
            PageBreak(),
            Paragraph(
                room.name + (" (deleted)" if room.deleted else ""),
                self.stylesheet["Heading2"],
            ),
            # todo: average time spent per user
        ]

        tstyledata = [
            ("ALIGN", (0, 0), (-1, 0), "LEFT"),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("BOX", (0, 0), (-1, -1), 0.25, colors.black),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
        ]

        rvqs = RoomView.objects.exclude(
            Q(end__lt=self.date_begin) | Q(start__gt=self.date_end)
        )

        unique_users = rvqs.filter(room=room).values("user")
        users_with_duration = User.objects.filter(id__in=unique_users,).annotate(
            total_duration=Subquery(
                rvqs.filter(
                    user=OuterRef("pk"),
                    room=room,
                )
                .values("room")
                .order_by()
                .annotate(
                    total_duration=Sum(
                        ExpressionWrapper(
                            F("end") - F("start"),
                            output_field=models.DurationField(),
                        )
                    )
                )
                .values("total_duration")
            )
        )
        aggs = users_with_duration.aggregate(a=Avg("total_duration"))

        tdata = [
            [_("Total number of unique viewers"), str(unique_users.distinct().count())],
            [_("Average time spent in room"), str(aggs["a"] or 0)],
            [
                _("Median time spent in room"),
                str(median_value(users_with_duration, "total_duration") or 0),
            ],
        ]
        if Channel.objects.filter(room=room).exists():
            tdata += [
                [
                    _("Number of chat messages"),
                    str(
                        ChatEvent.objects.filter(
                            timestamp__gte=self.date_begin,
                            timestamp__lte=self.date_end,
                            event_type="channel.message",
                            channel__room=room,
                        ).count()
                    ),
                ],
                [
                    _("Number of users who sent chat messages"),
                    str(
                        ChatEvent.objects.filter(
                            timestamp__gte=self.date_begin,
                            timestamp__lte=self.date_end,
                            event_type="channel.message",
                            channel__room=room,
                        )
                        .values("sender")
                        .distinct()
                        .count()
                    ),
                ],
            ]

        w = self.pagesize[0] - 30 * mm
        colwidths = [0.8 * w, 0.2 * w]
        table = Table(tdata, colWidths=colwidths, repeatRows=1)
        table.setStyle(TableStyle(tstyledata))
        s.append(table)

        day = self.date_begin
        while day.date() <= self.date_end.date():
            if self.day_whitelist is not None and day.date() not in self.day_whitelist:
                day += timedelta(days=1)
                continue
            fig = Figure(figsize=(7, 4))
            gds = day.replace(hour=self.date_begin.hour, minute=0, second=0)
            gde = day.replace(
                hour=self.date_end.hour, minute=self.date_end.minute, second=0
            )
            build_room_view_fig(fig, room, gds, gde, self.tz)
            s.append(
                KeepTogether(
                    [
                        Paragraph(
                            date_format(day, "SHORT_DATE_FORMAT"),
                            self.stylesheet["Heading3"],
                        ),
                        self._graph(fig),
                    ]
                )
            )
            day += timedelta(days=1)
        return s

    def story_for_exhibitors(self):
        s = [
            Paragraph(_("Exhibitors"), self.stylesheet["Heading2"]),
        ]
        tstyledata = [
            ("ALIGN", (0, 0), (-1, 0), "LEFT"),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("BOX", (0, 0), (-1, -1), 0.25, colors.black),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
        ]

        tdata = [
            [_("Exhibitor"), _("Views"), _("Unique viewers"), _("Contact requests")]
        ]

        qs = self.world.exhibitors.annotate(
            c_views=Subquery(
                ExhibitorView.objects.filter(
                    exhibitor=OuterRef("pk"),
                    datetime__gte=self.date_begin,
                    datetime__lte=self.date_end,
                )
                .order_by()
                .values("exhibitor")
                .annotate(c=Count("*"))
                .values("c")
            ),
            c_unique_viewers=Subquery(
                ExhibitorView.objects.filter(
                    exhibitor=OuterRef("pk"),
                    datetime__gte=self.date_begin,
                    datetime__lte=self.date_end,
                )
                .order_by()
                .values("exhibitor")
                .annotate(c=Count("user", distinct=True))
                .values("c")
            ),
            c_contact_requests=Subquery(
                ContactRequest.objects.filter(
                    exhibitor=OuterRef("pk"),
                    timestamp__gte=self.date_begin,
                    timestamp__lte=self.date_end,
                )
                .order_by()
                .values("exhibitor")
                .annotate(c=Count("*"))
                .values("c")
            ),
        )
        for e in qs:
            tdata.append(
                [
                    Paragraph(e.name, self.stylesheet["Normal"]),
                    str(e.c_views or 0),
                    str(e.c_unique_viewers or 0),
                    str(e.c_contact_requests or 0),
                ]
            )
        tdata.append(
            [
                _("Sum"),
                str(sum(e.c_views or 0 for e in qs)),
                str(sum(e.c_unique_viewers or 0 for e in qs)),
                str(sum(e.c_contact_requests or 0 for e in qs)),
            ]
        )

        w = self.pagesize[0] - 30 * mm
        colwidths = [0.4 * w, 0.2 * w, 0.2 * w, 0.2 * w]
        table = Table(tdata, colWidths=colwidths, repeatRows=1)
        table.setStyle(TableStyle(tstyledata))
        s.append(table)
        return s

    def global_sums(self):
        s = []
        tstyledata = [
            ("ALIGN", (0, 0), (-1, 0), "LEFT"),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("BOX", (0, 0), (-1, -1), 0.25, colors.black),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
        ]

        tdata = [
            [
                _("Report timeframe start"),
                date_format(self.date_begin, "SHORT_DATETIME_FORMAT"),
            ],
            [
                _("Report timeframe end"),
                date_format(self.date_end, "SHORT_DATETIME_FORMAT"),
            ],
            [_("Number of users (total)"), str(self.world.user_set.count())],
            [
                _("Users with authenticated access (total)"),
                str(self.world.user_set.filter(token_id__isnull=False).count()),
            ],
            [
                _("Exhibitors (total)"),
                str(self.world.exhibitors.count()),
            ],
            [
                _(
                    "Number of chat messages in streams and chat channels (in timeframe)"
                ),
                str(
                    ChatEvent.objects.filter(
                        channel__world=self.world,
                        event_type="channel.message",
                        channel__room__isnull=False,
                        timestamp__gte=self.date_begin,
                        timestamp__lte=self.date_end,
                    ).count()
                ),
            ],
            [
                _("Number of direct message channels (total)"),
                str(
                    Channel.objects.filter(world=self.world, room__isnull=True).count()
                ),
            ],
            [
                _("Number of chat messages in direct messages (in timeframe)"),
                str(
                    ChatEvent.objects.filter(
                        channel__world=self.world,
                        event_type="channel.message",
                        channel__room__isnull=True,
                        timestamp__gte=self.date_begin,
                        timestamp__lte=self.date_end,
                    ).count()
                ),
            ],
            [
                _("Number of 1:1 call attempts (in timeframe)"),
                str(
                    ChatEvent.objects.filter(
                        channel__world=self.world,
                        event_type="channel.message",
                        channel__room__isnull=True,
                        content__type="call",
                        timestamp__gte=self.date_begin,
                        timestamp__lte=self.date_end,
                    ).count()
                ),
            ],
        ]

        w = self.pagesize[0] - 30 * mm
        colwidths = [0.8 * w, 0.2 * w]
        table = Table(tdata, colWidths=colwidths, repeatRows=1)
        table.setStyle(TableStyle(tstyledata))
        s.append(table)

        day = self.date_begin
        while day.date() <= self.date_end.date():
            if self.day_whitelist is not None and day.date() not in self.day_whitelist:
                day += timedelta(days=1)
                continue
            fig = Figure(figsize=(7, 4))
            gds = day.replace(hour=self.date_begin.hour, minute=0, second=0)
            gde = day.replace(
                hour=self.date_end.hour, minute=self.date_end.minute, second=0
            )
            build_room_view_fig(fig, self.world, gds, gde, self.tz)
            s.append(
                KeepTogether(
                    [
                        Paragraph(
                            date_format(day, "SHORT_DATE_FORMAT"),
                            self.stylesheet["Heading3"],
                        ),
                        Paragraph(
                            "Counts the number of people currently either in a video room or live stream room."
                            "Does not count people only watching static pages or pure-text channels.",
                            self.stylesheet["Normal"],
                        ),
                        self._graph(fig),
                    ]
                )
            )
            day += timedelta(days=1)

        return s

    def _graph(self, fig):
        if self.pdf_graphs:
            imgdata = io.BytesIO()
            fig.savefig(imgdata, format="PDF")
            return PdfImage(imgdata)
        else:
            imgdata = io.BytesIO()
            fig.savefig(imgdata, dpi=600, format="PNG")
            imgdata.seek(0)
            w = self.pagesize[0] - 30 * mm
            return Image(
                imgdata, width=w, height=fig.get_figheight() / fig.get_figwidth() * w
            )
