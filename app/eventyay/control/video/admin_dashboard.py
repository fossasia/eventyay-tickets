from dataclasses import dataclass

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import (
    BBBServer,
    JanusServer,
    JitsiServer,
    LoungeMeshServer,
    TurnServer,
)


@dataclass(frozen=True)
class VideoServerConfig:
    model: object
    label: str
    list_url_name: str
    update_url_name: str
    order_by: str
    display_attr: str
    action_prefix: str


VIDEO_SERVER_CONFIGS = {
    "bbb": VideoServerConfig(
        model=BBBServer,
        label=_("BBB"),
        list_url_name="eventyay_admin:video_admin:settings",
        update_url_name="eventyay_admin:video_admin:bbbserver.update",
        order_by="url",
        display_attr="url",
        action_prefix="bbbserver",
    ),
    "janus": VideoServerConfig(
        model=JanusServer,
        label=_("Janus"),
        list_url_name="eventyay_admin:video_admin:settings",
        update_url_name="eventyay_admin:video_admin:janusserver.update",
        order_by="url",
        display_attr="url",
        action_prefix="janusserver",
    ),
    "jitsi": VideoServerConfig(
        model=JitsiServer,
        label=_("Jitsi"),
        list_url_name="eventyay_admin:video_admin:settings",
        update_url_name="eventyay_admin:video_admin:jitsiserver.update",
        order_by="url",
        display_attr="url",
        action_prefix="jitsiserver",
    ),
    "turn": VideoServerConfig(
        model=TurnServer,
        label=_("TURN"),
        list_url_name="eventyay_admin:video_admin:settings",
        update_url_name="eventyay_admin:video_admin:turnserver.update",
        order_by="hostname",
        display_attr="hostname",
        action_prefix="turnserver",
    ),
    "loungemesh": VideoServerConfig(
        model=LoungeMeshServer,
        label=_("LoungeMesh"),
        list_url_name="eventyay_admin:video_admin:settings",
        update_url_name="eventyay_admin:video_admin:loungemeshserver.update",
        order_by="url",
        display_attr="url",
        action_prefix="loungemeshserver",
    ),
}


def get_video_server_config(server_type):
    return VIDEO_SERVER_CONFIGS.get(server_type)


def get_video_server_dashboard_rows():
    rows = []
    for server_type, config in VIDEO_SERVER_CONFIGS.items():
        queryset = config.model.objects.all().order_by(config.order_by)
        # event_exclusive is a nullable ForeignKey on BBB/Janus/Jitsi/TURN.
        # Prefer the model field check over getattr so we never touch a reverse
        # OneToOne that could raise.
        has_event_exclusive = any(
            field.name == "event_exclusive" for field in config.model._meta.fields
        )
        if has_event_exclusive:
            queryset = queryset.select_related("event_exclusive")
        queryset = queryset.prefetch_related("organizers", "events")

        for server in queryset:
            active = bool(server.active)
            rows.append(
                {
                    "server": server,
                    "server_type": server_type,
                    "type_label": config.label,
                    "name": getattr(server, config.display_attr),
                    "event_exclusive": server.event_exclusive if has_event_exclusive else None,
                    "organizers": list(server.organizers.all()),
                    "events": list(server.events.all()),
                    "edit_url": reverse(
                        config.update_url_name, kwargs={"pk": server.pk}
                    ),
                    "list_url": reverse(config.list_url_name) + f"?tab={server_type}",
                    "toggle_url": reverse(
                        "eventyay_admin:video_admin:server.toggle-active",
                        kwargs={"server_type": server_type, "pk": server.pk},
                    ),
                    "active": active,
                    "status": _("Active") if active else _("Inactive"),
                }
            )
    return rows
