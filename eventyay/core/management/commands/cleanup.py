import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import F
from django.utils.timezone import now

from eventyay.base.models import RouletteRequest
from eventyay.base.models.auth import ShortToken
from eventyay.base.models.room import AnonymousInvite, RoomView
from eventyay.base.models.event import EventView
from eventyay.base.models.storage_model import StoredFile

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Perform cleanup tasks"

    def handle(self, *args, **options):
        self._cleanup_views()
        self._cleanup_files()
        self._cleanup_tokens()

    def _cleanup_files(self):
        for f in StoredFile.objects.filter(expires__isnull=False, expires__lt=now()):
            if f.file:
                f.file.delete(False)
            f.delete()

    def _cleanup_views(self):
        # Reset RoomView objects that never "ended". In the unlikely event the session *is* still open, this will
        # *temporarily* break the statistics, but it will be auto-corrected as soon as ``end_view`` is properly
        # called.
        RoomView.objects.filter(
            end__isnull=True, start__lt=now() - timedelta(hours=6)
        ).update(end=F("start") + timedelta(hours=1))
        RoomView.objects.filter(
            end__isnull=False, room__event__config__track_room_views=False
        ).delete()

        EventView.objects.filter(
            end__isnull=True, start__lt=now() - timedelta(hours=24)
        ).update(end=F("start") + timedelta(hours=4))
        EventView.objects.filter(
            end__isnull=False, event__config__track_event_views=False
        ).delete()

        RouletteRequest.objects.filter(expiry__lte=now() - timedelta(hours=1)).delete()

    def _cleanup_tokens(self):
        ShortToken.objects.filter(expires__lte=now() - timedelta(days=90)).delete()
        AnonymousInvite.objects.filter(expires__lte=now() - timedelta(days=90)).delete()
