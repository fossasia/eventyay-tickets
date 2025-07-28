from datetime import datetime, time, timedelta

import pytz
from django.core.management.base import BaseCommand
from django.db.models import Max, Q
from django.utils.timezone import now

from eventyay.base.models import ChatEvent, RoomView, Event


class Command(BaseCommand):
    help = "Clear all non-config data from events that have not been used in a while"

    def add_arguments(self, parser):
        parser.add_argument("days", type=int)

    def handle(self, *args, **options):
        cutoff = now() - timedelta(days=options["days"])
        qs = (
            Event.objects.annotate(
                max_login=Max("user__last_login"),
            )
            .filter(domain__isnull=False)
            .filter(Q(Q(max_login__isnull=True) | Q(max_login__lt=cutoff)))
            .order_by("max_login")
        )

        for event in qs:
            planned_end = event.planned_usages.aggregate(m=Max("end"))["m"]
            checks = [
                # Check that this event *really* had no activity recently
                event.audit_logs.aggregate(m=Max("timestamp"))["m"],
                event.views.aggregate(m=Max("start"))["m"],
                RoomView.objects.filter(room__event=event).aggregate(m=Max("start"))[
                    "m"
                ],
                ChatEvent.objects.filter(channel__event=event).aggregate(
                    m=Max("timestamp")
                )["m"],
                (
                    pytz.UTC.localize(datetime.combine(planned_end, time(0)))
                    if planned_end
                    else None
                ),
            ]
            checks = [c for c in checks if c]
            if checks and max(checks) > cutoff:
                continue

            event.clear_data()
