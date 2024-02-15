import hashlib
import logging
import textwrap
from urllib.parse import unquote

from django.contrib import messages
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseNotModified,
    HttpResponsePermanentRedirect,
    HttpResponseRedirect,
)
from django.urls import resolve, reverse
from django.utils.functional import cached_property
from django.utils.translation import activate
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from django_context_decorator import context

from pretalx.common.mixins.views import EventPermissionRequired
from pretalx.common.signals import register_data_exporters
from pretalx.common.utils import safe_filename
from pretalx.schedule.ascii import draw_ascii_schedule
from pretalx.schedule.exporters import ScheduleData

logger = logging.getLogger(__name__)


class ScheduleMixin:
    @cached_property
    def version(self):
        if "version" in self.kwargs:
            return unquote(self.kwargs["version"])
        return None

    def get_object(self):
        if self.version:
            return self.request.event.schedules.filter(
                version__iexact=self.version
            ).first()
        return self.request.event.current_schedule

    @context
    @cached_property
    def schedule(self):
        return self.get_object()

    def dispatch(self, request, *args, **kwargs):
        if "version" in request.GET:
            kwargs["version"] = request.GET["version"]
            return HttpResponsePermanentRedirect(
                reverse(
                    f"agenda:versioned-{request.resolver_match.url_name}",
                    args=args,
                    kwargs=kwargs,
                )
            )
        return super().dispatch(request, *args, **kwargs)


class ExporterView(EventPermissionRequired, ScheduleMixin, TemplateView):
    permission_required = "agenda.view_schedule"

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        schedule = self.schedule

        if not schedule and self.version:
            result["version"] = self.version
            result["error"] = f'Schedule "{self.version}" not found.'
            return result
        if not schedule:
            result["error"] = "Schedule not found."
            return result
        result["schedules"] = self.request.event.schedules.filter(
            published__isnull=False
        ).values_list("version")
        return result

    def get_exporter(self, request):
        url = resolve(request.path_info)

        if url.url_name == "export":
            exporter = url.kwargs.get("name") or unquote(
                self.request.GET.get("exporter")
            )
        else:
            exporter = url.url_name

        exporter = (
            exporter[len("export.") :] if exporter.startswith("export.") else exporter
        )
        responses = register_data_exporters.send(request.event)
        for __, response in responses:
            ex = response(request.event)
            if ex.identifier == exporter:
                if ex.public or request.is_orga:
                    return ex

    def get(self, request, *args, **kwargs):
        exporter = self.get_exporter(request)
        if not exporter:
            raise Http404()
        lang_code = request.GET.get("lang")
        if lang_code and lang_code in request.event.locales:
            activate(lang_code)
        elif "lang" in request.GET:
            activate(request.event.locale)

        exporter.schedule = self.schedule
        exporter.is_orga = getattr(self.request, "is_orga", False)

        try:
            file_name, file_type, data = exporter.render()
            etag = hashlib.sha1(str(data).encode()).hexdigest()
        except Exception:
            logger.exception(
                f"Failed to use {exporter.identifier} for {self.request.event.slug}"
            )
            raise Http404()
        if "If-None-Match" in request.headers:
            if request.headers["If-None-Match"] == etag:
                return HttpResponseNotModified()
        headers = {"ETag": etag}
        if file_type not in ["application/json", "text/xml"]:
            headers["Content-Disposition"] = (
                f'attachment; filename="{safe_filename(file_name)}"'
            )
        if exporter.cors:
            headers["Access-Control-Allow-Origin"] = exporter.cors
        return HttpResponse(data, content_type=file_type, headers=headers)


class ScheduleView(EventPermissionRequired, ScheduleMixin, TemplateView):
    template_name = "agenda/schedule.html"

    def get_permission_required(self):
        if self.version == "wip":
            return ["orga.view_schedule"]
        return ["agenda.view_schedule"]

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
        if output_format not in ["list", "table"]:
            output_format = "table"
        result = draw_ascii_schedule(data, output_format=output_format)
        return HttpResponse(
            response_start + result, content_type="text/plain; charset=utf-8"
        )

    def dispatch(self, request, **kwargs):
        if not self.has_permission() and self.request.user.has_perm(
            "agenda.view_featured_submissions", self.request.event
        ):
            messages.success(request, _("Our schedule is not live yet."))
            return HttpResponseRedirect(self.request.event.urls.featured)
        return super().dispatch(request, **kwargs)

    def get(self, request, **kwargs):
        accept_header = request.headers.get("Accept", "")

        if getattr(self, "is_html_export", False) or "text/html" in accept_header:
            return super().get(request, **kwargs)

        if not accept_header or accept_header in ("plain", "text/plain"):
            return self.get_text(request, **kwargs)

        export_headers = {
            "frab_xml": ["application/xml", "text/xml"],
            "frab_json": ["application/json"],
        }
        for url_name, headers in export_headers.items():
            if any(header in accept_header for header in headers):
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

    @context
    def exporters(self):
        return list(
            exporter(self.request.event)
            for _, exporter in register_data_exporters.send(self.request.event)
        )

    @context
    def show_talk_list(self):
        return (
            self.request.path.endswith("/talk/")
            or self.request.event.display_settings["schedule"] == "list"
        )


class ScheduleNoJsView(ScheduleView):
    template_name = "agenda/schedule_nojs.html"

    def get_schedule_data(self):
        data = ScheduleData(
            event=self.request.event,
            schedule=self.schedule,
            with_accepted=self.schedule and not self.schedule.version,
            with_breaks=True,
        ).data
        for date in data:
            rooms = date.pop("rooms")
            talks = [talk for room in rooms for talk in room.get("talks", [])]
            talks.sort(
                key=lambda x: (x.start, x.submission.title if x.submission else "")
            )
            date["talks"] = talks
        return {"data": list(data)}

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        if "schedule" not in result:
            return result

        result.update(**self.get_schedule_data())
        result["day_count"] = len(result["data"])
        return result


class ChangelogView(EventPermissionRequired, TemplateView):
    template_name = "agenda/changelog.html"
    permission_required = "agenda.view_schedule"
