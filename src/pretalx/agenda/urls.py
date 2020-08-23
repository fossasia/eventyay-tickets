from django.conf.urls import include
from django.urls import re_path

from pretalx.common.views import get_static
from pretalx.event.models.event import SLUG_CHARS

from .views import featured, feed, schedule, speaker, talk, widget


def get_schedule_urls(regex_prefix, name_prefix=""):
    """given a prefix (e.g. /schedule) generate matching schedule-URLs (e.g.

    /schedule.json, /schedule/feed.xml, ...)
    """

    regex_prefix = regex_prefix.rstrip("/")

    return [
        re_path(f"{regex_prefix}{regex}", view, name=f"{name_prefix}{name}")
        for regex, view, name in [
            ("/$", schedule.ScheduleView.as_view(), "schedule"),
            (".xml$", schedule.ExporterView.as_view(), "export.schedule.xml"),
            (".xcal$", schedule.ExporterView.as_view(), "export.schedule.xcal"),
            (".json$", schedule.ExporterView.as_view(), "export.schedule.json"),
            (".ics$", schedule.ExporterView.as_view(), "export.schedule.ics"),
            (
                "/export/(?P<name>[A-Za-z.-]+)$",
                schedule.ExporterView.as_view(),
                "export",
            ),
        ]
    ]


app_name = "agenda"
urlpatterns = [
    re_path(
        fr"^(?P<event>[{SLUG_CHARS}]+)/",
        include(
            [
                re_path(
                    r"^schedule/changelog/$",
                    schedule.ChangelogView.as_view(),
                    name="schedule.changelog",
                ),
                re_path(r"^schedule/feed.xml$", feed.ScheduleFeed(), name="feed"),
                re_path(
                    r"^schedule/widget/v(?P<version>[0-9]+).(?P<locale>[a-z]{2}).js$",
                    widget.widget_script,
                    name="widget.script",
                ),
                re_path(
                    r"^schedule/widget/v(?P<version>[0-9]+).css$",
                    widget.widget_style,
                    name="widget.style",
                ),
                re_path(
                    r"^schedule/widget/v1.json$",
                    widget.WidgetData.as_view(),
                    name="widget.data",
                ),
                re_path(
                    r"^schedule/widget/v2.json$",
                    widget.widget_data_v2,
                    name="widget.data.2",
                ),
                *get_schedule_urls("^schedule"),
                *get_schedule_urls("^schedule/v/(?P<version>.+)", "versioned-"),
                re_path(r"^sneak/$", featured.sneakpeek_redirect, name="oldsneak"),
                re_path(
                    r"^featured/$", featured.FeaturedView.as_view(), name="featured"
                ),
                re_path(r"^speaker/$", talk.SpeakerList.as_view(), name="speakers"),
                re_path(
                    r"^speaker/by-id/(?P<pk>\d+)/$",
                    speaker.SpeakerRedirect.as_view(),
                    name="speaker.redirect",
                ),
                re_path(r"^talk/$", talk.TalkList.as_view(), name="talks"),
                re_path(r"^talk/(?P<slug>\w+)/$", talk.TalkView.as_view(), name="talk"),
                re_path(
                    r"^talk/(?P<slug>\w+)/feedback/$",
                    talk.FeedbackView.as_view(),
                    name="feedback",
                ),
                re_path(
                    r"^talk/(?P<slug>\w+).ics$",
                    talk.SingleICalView.as_view(),
                    name="ical",
                ),
                re_path(
                    r"^talk/review/(?P<slug>\w+)$",
                    talk.TalkReviewView.as_view(),
                    name="review",
                ),
                re_path(
                    r"^speaker/(?P<code>\w+)/$",
                    speaker.SpeakerView.as_view(),
                    name="speaker",
                ),
                re_path(
                    r"^speaker/(?P<code>\w+)/talks.ics$",
                    speaker.SpeakerTalksIcalView.as_view(),
                    name="speaker.talks.ical",
                ),
            ]
        ),
    ),
    re_path(
        r"^sw.js",
        get_static,
        {
            "path": "agenda/js/serviceworker.js",
            "content_type": "application/javascript",
        },
    ),
]
