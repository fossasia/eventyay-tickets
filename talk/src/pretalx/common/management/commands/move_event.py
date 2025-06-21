import datetime as dt

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F
from django.utils.timezone import now
from django_scopes import scope

from pretalx.event.models import Event
from pretalx.schedule.models import TalkSlot


class Command(BaseCommand):
    help = "Move an event to a given date (default: today)"

    def add_arguments(self, parser):
        parser.add_argument("--event", type=str, help="Slug of the event to be used.")
        parser.add_argument(
            "--date", type=str, help="Date in the format YYYY-MM-DD. Default: today"
        )

    @transaction.atomic
    def handle(self, *args, **options):
        event_slug = options.get("event")
        start_date = options.get("date")

        if start_date:
            start_date = dt.datetime.strptime(start_date, "%Y-%m-%d").date()
        else:
            start_date = now().date()

        event = Event.objects.get(slug=event_slug)

        with scope(event=event):
            days_delta = start_date - event.date_from
            if days_delta.days:
                event.date_from += days_delta
                event.date_to += days_delta
                event.save()
                TalkSlot.objects.filter(
                    schedule__event=event, start__isnull=False
                ).update(start=F("start") + days_delta)
                TalkSlot.objects.filter(
                    schedule__event=event, end__isnull=False
                ).update(end=F("end") + days_delta)
