import json
import textwrap
from contextlib import suppress
from urllib.parse import unquote

from django.contrib import messages
from django.http import (
    Http404,
    HttpResponse,
    HttpResponsePermanentRedirect,
    HttpResponseRedirect,
)
from django.urls import resolve, reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import cache_page
from django.views.generic import TemplateView
from django_context_decorator import context

from eventyay.agenda.views.utils import (
    get_schedule_exporter_content,
    get_schedule_exporters,
)
from eventyay.common.signals import register_my_data_exporters
from eventyay.common.views.mixins import EventPermissionRequired, PermissionRequired
from eventyay.schedule.ascii import draw_ascii_schedule
from eventyay.schedule.exporters import ScheduleData
from eventyay.base.models.submission import SubmissionFavouriteDeprecated


class ScheduleMixin:
    @cached_property
    def version(self):
        if version := self.kwargs.get("version"):
            return unquote(version)
        return None

    def get_object(self):
        schedule = None
        if self.version:
            with suppress(Exception):
                schedule = (
                    self.request.event.schedules.filter(version__iexact=self.version)
                    .select_related("event")
                    .first()
                )
        schedule = schedule or self.request.event.current_schedule
        if schedule:
            # make use of existing caches and prefetches
            schedule.event = self.request.event
        return schedule

    @cached_property
    def object(self):
        return self.get_object()

    @context
    @cached_property
    def schedule(self):
        return self.object

    def dispatch(self, request, *args, **kwargs):
        if version := request.GET.get("version"):
            kwargs["version"] = version
            return HttpResponsePermanentRedirect(
                reverse(
                    f"agenda:versioned-{request.resolver_match.url_name}",
                    args=args,
                    kwargs=kwargs,
                )
            )
        return super().dispatch(request, *args, **kwargs)


class ExporterView(EventPermissionRequired, ScheduleMixin, TemplateView):
    permission_required = "schedule.list_schedule"

    def get(self, request, *args, **kwargs):
        url = resolve(self.request.path_info)
        if url.url_name == "export":
            name = url.kwargs.get("name") or unquote(self.request.GET.get("exporter"))
        else:
            name = url.url_name

        if name.startswith("export."):
            name = name[len("export.") :]
        response = get_schedule_exporter_content(request, name, self.schedule)
        if not response:
            raise Http404()
        return response


class ScheduleView(PermissionRequired, ScheduleMixin, TemplateView):
    template_name = "agenda/schedule.html"
    permission_required = "schedule.view_schedule"

    def get_text(self, request, **kwargs):
        data = ScheduleData(
            event=self.request.event,
            schedule=self.schedule,
            with_accepted=False,
            with_breaks=True,
        ).data
        response_start = textwrap.dedent(
            f"""
        \033[1m{request.event.name}\033[0m

        Get different formats:
           curl {request.event.urls.schedule.full()}\\?format=table (default)
           curl {request.event.urls.schedule.full()}\\?format=list

        """
        )
        output_format = request.GET.get("format", "table")
        if output_format not in ("list", "table"):
            output_format = "table"
        try:
            result = draw_ascii_schedule(data, output_format=output_format)
        except StopIteration:  # pragma: no cover
            result = draw_ascii_schedule(data, output_format="list")
        result += "\n\n  📆 powered by eventyay"
        return HttpResponse(
            response_start + result, content_type="text/plain; charset=utf-8"
        )

    def dispatch(self, request, **kwargs):
        if not self.has_permission() and self.request.user.has_perm(
            "submission.list_featured_submission", self.request.event
        ):
            messages.success(request, _("Our schedule is not live yet."))
            return HttpResponseRedirect(self.request.event.urls.featured)
        return super().dispatch(request, **kwargs)

    def get(self, request, **kwargs):
        accept_header = request.headers.get("Accept") or ""
        if getattr(self, "is_html_export", False) or (
            accept_header and request.accepts("text/html")
        ):
            return super().get(request, **kwargs)

        if not accept_header or request.accepts("text/plain"):
            return self.get_text(request, **kwargs)

        export_headers = {
            "frab_xml": ["application/xml", "text/xml"],
            "frab_json": ["application/json"],
        }
        for url_name, headers in export_headers.items():
            if any(request.accepts(header) for header in headers):
                target_url = getattr(self.request.event.urls, url_name).full()
                response = HttpResponseRedirect(target_url)
                response.status_code = 303
                return response

        if "*/*" in accept_header:
            return self.get_text(request, **kwargs)
        return super().get(request, **kwargs)  # Fallback to standard HTML response

    def get_object(self):
        if self.version == "wip":
            return self.request.event.wip_schedule
        schedule = super().get_object()
        if not schedule:
            raise Http404()
        return schedule

    def get_permission_object(self):
        return self.object

    @context
    def exporters(self):
        return [
            exporter
            for exporter in get_schedule_exporters(self.request, public=True)
            if exporter.show_public
        ]

    @context
    def my_exporters(self):
        return list(
            exporter(self.request.event)
            for _, exporter in register_my_data_exporters.send(self.request.event)
        )

    @context
    def show_talk_list(self):
        return (
            self.request.path.endswith("/talk/")
            or self.request.event.display_settings["schedule"] == "list"
        )


@cache_page(60 * 60 * 24)
def schedule_messages(request, **kwargs):
    """This view is cached for a day, as it is small and non-critical, but loaded synchronously."""
    strings = {
        "favs_not_logged_in": _(
            "You're currently not logged in, so your favourited talks will only be stored locally in your browser."
        ),
        "favs_not_saved": _(
            "Your favourites could only be saved locally in your browser."
        ),
    }
    strings = {key: str(value) for key, value in strings.items()}
    return HttpResponse(
        f"const EVENTYAY_MESSAGES = {json.dumps(strings)};",
        content_type="application/javascript",
    )


def talk_sort_key(talk):
    return (talk.start, talk.submission.title if talk.submission else "")


class ScheduleNoJsView(ScheduleView):
    template_name = "agenda/schedule_nojs.html"

    def get_schedule_data(self):
        schedule = self.get_object()
        data = ScheduleData(
            event=self.request.event,
            schedule=schedule,
            with_accepted=schedule and not schedule.version,
            with_breaks=True,
        ).data
        for date in data:
            rooms = date.pop("rooms")
            talks = [talk for room in rooms for talk in room.get("talks", [])]
            talks.sort(key=talk_sort_key)
            date["talks"] = talks
        return {"data": list(data)}

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        result.update(**self.get_schedule_data())
        result["day_count"] = len(result.get("data", []))
        return result


class ChangelogView(EventPermissionRequired, TemplateView):
    template_name = "agenda/changelog.html"
    permission_required = "schedule.list_schedule"

    @context
    def schedules(self):
        return (
            self.request.event.schedules.all()
            .filter(version__isnull=False)
            .select_related("event")
        )
