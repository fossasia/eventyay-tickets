import datetime
import uuid

import jwt
from django.core.management.base import BaseCommand
from django.utils.crypto import get_random_string

from venueless.core.models import Channel, ChatEvent, Membership, World
from venueless.core.models.exhibitor import (
    ContactRequest,
    ExhibitorStaff,
    ExhibitorView,
)
from venueless.core.models.room import Reaction, RoomView
from venueless.storage.models import StoredFile


class Command(BaseCommand):
    help = "Clear all non-config data from a world"

    def add_arguments(self, parser):
        parser.add_argument("world_id", type=str)

    def handle(self, *args, **options):
        w = World.objects.get(id=options["world_id"])
        w.audit_logs.all().delete()
        w.world_grants.all().delete()
        w.room_grants.all().delete()
        w.bbb_calls.all().delete()
        ChatEvent.objects.filter(channel__world=w).delete()
        Membership.objects.filter(channel__world=w).delete()
        ExhibitorStaff.objects.filter(exhibitor__world=w).delete()
        ContactRequest.objects.filter(exhibitor__world=w).delete()
        ExhibitorView.objects.filter(exhibitor__world=w).delete()
        Reaction.objects.filter(room__world=w).delete()
        RoomView.objects.filter(room__world=w).delete()

        for f in StoredFile.objects.filter():
            if f.file:
                f.file.delete(False)
            f.delete()

        w.user_set.all().delete()
