from datetime import datetime, time, timedelta

import pytz
from django.core.management.base import BaseCommand
from django.db.models import Max, Q
from django.utils.timezone import now

from venueless.core.models import ChatEvent, RoomView, World


class Command(BaseCommand):
    help = "Clear all non-config data from worlds that have not been used in a while"

    def add_arguments(self, parser):
        parser.add_argument("days", type=int)

    def handle(self, *args, **options):
        cutoff = now() - timedelta(days=options["days"])
        qs = (
            World.objects.annotate(
                max_login=Max("user__last_login"),
            )
            .filter(domain__isnull=False)
            .filter(Q(Q(max_login__isnull=True) | Q(max_login__lt=cutoff)))
            .order_by("max_login")
        )

        for world in qs:
            planned_end = world.planned_usages.aggregate(m=Max("end"))["m"]
            checks = [
                # Check that this world *really* had no activity recently
                world.audit_logs.aggregate(m=Max("timestamp"))["m"],
                world.views.aggregate(m=Max("start"))["m"],
                RoomView.objects.filter(room__world=world).aggregate(m=Max("start"))[
                    "m"
                ],
                ChatEvent.objects.filter(channel__world=world).aggregate(
                    m=Max("timestamp")
                )["m"],
                pytz.UTC.localize(datetime.combine(planned_end, time(0)))
                if planned_end
                else None,
            ]
            checks = [c for c in checks if c]
            if checks and max(checks) > cutoff:
                continue

            world.clear_data()
