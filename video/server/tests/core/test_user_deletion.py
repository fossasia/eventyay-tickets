import datetime
import os
import uuid

import pytest
from django.core.files.base import ContentFile
from django.utils.timezone import now

from venueless.core.models import (
    AuditLog,
    BBBCall,
    BBBServer,
    Channel,
    ChatEvent,
    Exhibitor,
    Membership,
    Poster,
    RoulettePairing,
    RouletteRequest,
)
from venueless.core.services.user import create_user, update_user
from venueless.storage.models import StoredFile


@pytest.mark.django_db
def test_delete_user(world, chat_room):
    u1 = create_user(world_id="sample", client_id="1234")
    u2 = create_user(world_id="sample", client_id="5678")
    should_be_deleted_after_u1_is_deleted = []

    bbb_server = BBBServer.objects.create(
        url="https://video1.pretix.eu/bigbluebutton/", secret="bogussecret", active=True
    )
    bbbcall = BBBCall.objects.create(server=bbb_server, world=world)
    bbbcall.invited_members.add(u1)
    bbbcall.invited_members.add(u2)

    sf = StoredFile.objects.create(
        id="004f2773-7b93-4011-b29a-953f6bf161df",
        world=world,
        date=now(),
        filename="Screenshot.png",
        type="image/png",
        file=ContentFile("", "Screenshot.png"),
        public=True,
        user=u2,
    )
    assert os.path.exists(sf.file.path)

    sf_avatar = StoredFile.objects.create(
        id="5693b299-c912-4941-8dc2-91981b37c1fc",
        world=world,
        date=now(),
        filename="avatar.png",
        type="image/png",
        file=ContentFile("", "avatar.png"),
        public=True,
        user=u1,
    )
    assert os.path.exists(sf_avatar.file.path)

    exhibitor = Exhibitor.objects.create(name="Foo", room=chat_room, world=world)
    poster = Poster.objects.create(title="Foo", parent_room=chat_room, world=world)
    public_channel = Channel.objects.get_or_create(room=chat_room, world=world)[0]
    dm_channel = Channel.objects.get_or_create(world=world, room=None)[0]

    should_be_deleted_after_u1_is_deleted.append(
        Membership.objects.create(user=u1, channel=public_channel)
    )
    Membership.objects.create(user=u2, channel=public_channel)
    Membership.objects.create(user=u1, channel=dm_channel)
    Membership.objects.create(user=u2, channel=dm_channel)
    should_be_deleted_after_u1_is_deleted.append(
        u1.room_grants.create(world=world, room=chat_room, role="test")
    )
    should_be_deleted_after_u1_is_deleted.append(
        u1.world_grants.create(world=world, role="test")
    )
    should_be_deleted_after_u1_is_deleted.append(
        RouletteRequest.objects.create(
            room=chat_room,
            user=u1,
            socket_id=uuid.uuid4(),
            expiry=now() + datetime.timedelta(minutes=5),
        )
    )
    should_be_deleted_after_u1_is_deleted.append(
        RoulettePairing.objects.create(room=chat_room, user1=u1, user2=u2)
    )
    should_be_deleted_after_u1_is_deleted.append(
        RoulettePairing.objects.create(room=chat_room, user1=u2, user2=u1)
    )
    should_be_deleted_after_u1_is_deleted.append(exhibitor.staff.create(user=u1))
    should_be_deleted_after_u1_is_deleted.append(poster.presenters.create(user=u1))
    assert update_user(
        "sample",
        str(u1.pk),
        public_data={
            "profile": {
                "display_name": "John Doe",
                "avatar": {
                    "url": "http://localhost:8375/media/pub/sample/5693b299-c912-4941-8dc2-91981b37c1fc.S50ehvbVo7fw.png"
                },
            }
        },
    )
    u1.refresh_from_db()
    log = AuditLog.objects.get(type="auth.user.profile.changed")
    assert log.data == {
        "object": str(u1.pk),
        "old": {},
        "new": {
            "display_name": "John Doe",
            "avatar": {
                "url": "http://localhost:8375/media/pub/sample/5693b299-c912-4941-8dc2-91981b37c1fc.S50ehvbVo7fw.png"
            },
        },
    }

    chat_message_u1_pub = public_channel.chat_events.create(
        id=1,
        event_type="channel.message",
        content={"body": "test", "type": "text"},
        sender=u1,
    )
    chat_message_u2_pub = public_channel.chat_events.create(
        id=2,
        event_type="channel.message",
        content={"body": "test", "type": "text"},
        sender=u2,
    )
    chat_message_u1_dm = dm_channel.chat_events.create(
        id=3,
        event_type="channel.message",
        content={"body": "test", "type": "text"},
        sender=u1,
    )
    chat_message_u2_dm = dm_channel.chat_events.create(
        id=4,
        event_type="channel.message",
        content={
            "body": "",
            "type": "files",
            "files": [
                {
                    "url": "http://localhost:8375/media/pub/sample/004f2773-7b93-4011-b29a-953f6bf161df.GDMA7F6iZUr9.png",
                    "name": "Screenshot.png",
                    "mimeType": "image/png",
                }
            ],
        },
        sender=u1,
    )

    u1.soft_delete()

    u1.refresh_from_db()
    assert u1.deleted
    assert not u1.client_id
    assert not u1.token_id
    assert not u1.show_publicly
    assert u1.profile == {}

    log.refresh_from_db()
    assert log.data == {
        "object": str(u1.pk),
        "old": {"__redacted": True},
        "new": {"__redacted": True},
    }

    assert bbbcall.invited_members.count() == 1
    for obj in should_be_deleted_after_u1_is_deleted:
        with pytest.raises(type(obj).DoesNotExist):
            # Make sure the object was deleted
            obj.refresh_from_db()

    # Messages stay
    chat_message_u1_pub.refresh_from_db()
    chat_message_u1_dm.refresh_from_db()

    u2.soft_delete()

    # DMs between u1 and u2 now get deleted too
    chat_message_u1_pub.refresh_from_db()
    chat_message_u2_pub.refresh_from_db()
    with pytest.raises(ChatEvent.DoesNotExist):
        chat_message_u1_dm.refresh_from_db()
    with pytest.raises(ChatEvent.DoesNotExist):
        chat_message_u2_dm.refresh_from_db()
    with pytest.raises(StoredFile.DoesNotExist):
        sf.refresh_from_db()
    with pytest.raises(Channel.DoesNotExist):
        dm_channel.refresh_from_db()
    assert not os.path.exists(sf.file.path)

    with pytest.raises(StoredFile.DoesNotExist):
        sf_avatar.refresh_from_db()
    assert not os.path.exists(sf_avatar.file.path)
