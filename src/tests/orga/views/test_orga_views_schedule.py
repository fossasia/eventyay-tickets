import datetime as dt
import json
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scope

from pretalx.schedule.models import Schedule


@pytest.mark.django_db
@pytest.mark.usefixtures("accepted_submission")
def test_talk_list(orga_client, event, break_slot):
    response = orga_client.get(
        reverse("orga:schedule.api.talks", kwargs={"event": event.slug}), follow=True
    )
    content = json.loads(response.content.decode())
    assert response.status_code == 200
    assert len(content["talks"]) == 2
    assert len([talk for talk in content["talks"] if talk["title"]])


@pytest.mark.django_db
def test_talk_schedule_api_create_break(orga_client, event, schedule, room):
    with scope(event=event):
        slot_count = event.wip_schedule.talks.count()
    response = orga_client.post(
        reverse("orga:schedule.api.talks", kwargs={"event": event.slug}),
        json.dumps({"room": room.pk, "duration": 50, "title": "Break"}),
        content_type="application/json",
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        assert event.wip_schedule.talks.count() == slot_count + 1
        slot = event.wip_schedule.talks.filter(submission__isnull=True).first()
        assert slot
        assert slot.description == "Break"
        assert slot.room == room
        assert slot.duration == 50


@pytest.mark.parametrize("with_room", (True, False))
@pytest.mark.django_db
def test_talk_schedule_api_update(orga_client, event, schedule, slot, room, with_room):
    with scope(event=event):
        slot = event.wip_schedule.talks.first()
        start = now()
        assert slot.start != start
    response = orga_client.patch(
        reverse(
            "orga:schedule.api.update", kwargs={"event": event.slug, "pk": slot.pk}
        ),
        data=json.dumps(
            {"room": room.pk if with_room else None, "start": start.isoformat()}
        ),
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        slot.refresh_from_db()
        content = json.loads(response.content.decode())
        assert content["title"] == slot.submission.title
        assert slot.start == start
        assert slot.room == room


@pytest.mark.django_db
def test_talk_schedule_api_update_wrong_slot(orga_client, event, schedule, slot):
    with scope(event=event):
        slot = event.wip_schedule.talks.first()
        start = now()
        assert slot.start != start
    response = orga_client.patch(
        reverse(
            "orga:schedule.api.update",
            kwargs={"event": event.slug, "pk": slot.pk + 100},
        ),
        data=json.dumps({"room": 100, "start": start.isoformat()}),
        follow=True,
    )
    assert response.status_code == 200
    assert response.json() == {"error": "Talk not found"}


@pytest.mark.django_db
def test_talk_schedule_api_update_break_slot(
    orga_client, event, schedule, break_slot, room
):
    with scope(event=event):
        slot = event.wip_schedule.talks.first()
        start = now()
        assert slot.start != start
    response = orga_client.patch(
        reverse(
            "orga:schedule.api.update", kwargs={"event": event.slug, "pk": slot.pk}
        ),
        data=json.dumps(
            {
                "room": room.pk,
                "start": start.isoformat(),
                "duration": 90,
                "title": "New break",
            }
        ),
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        slot.refresh_from_db()
        assert slot.duration == 90
        assert str(slot.description) == "New break"
        assert slot.start == start
        assert slot.room == room


@pytest.mark.django_db
def test_talk_schedule_api_update_break_slot_explicit_end(
    orga_client, event, schedule, break_slot, room
):
    with scope(event=event):
        slot = event.wip_schedule.talks.first()
        start = now()
        assert slot.start != start
    response = orga_client.patch(
        reverse(
            "orga:schedule.api.update", kwargs={"event": event.slug, "pk": slot.pk}
        ),
        data=json.dumps(
            {
                "room": room.pk,
                "start": start.isoformat(),
                "end": (start + dt.timedelta(minutes=90)).isoformat(),
                "title": "New break",
            }
        ),
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        slot.refresh_from_db()
        assert slot.duration == 90
        assert str(slot.description) == "New break"
        assert slot.start == start
        assert slot.room == room


@pytest.mark.django_db
def test_talk_schedule_api_update_break_slot_no_duration(
    orga_client, event, schedule, break_slot, room
):
    with scope(event=event):
        slot = event.wip_schedule.talks.first()
        start = now()
        assert slot.start != start
        previous_duration = slot.duration
    response = orga_client.patch(
        reverse(
            "orga:schedule.api.update", kwargs={"event": event.slug, "pk": slot.pk}
        ),
        data=json.dumps({"room": room.pk, "start": start.isoformat()}),
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        slot.refresh_from_db()
        assert slot.duration == previous_duration
        assert slot.start == start
        assert slot.room == room


@pytest.mark.django_db
def test_talk_schedule_api_delete_slot(orga_client, event, schedule, break_slot):
    with scope(event=event):
        slot = event.wip_schedule.talks.first()
        slot_count = event.wip_schedule.talks.count()
    response = orga_client.delete(
        reverse(
            "orga:schedule.api.update", kwargs={"event": event.slug, "pk": slot.pk}
        ),
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        assert event.wip_schedule.talks.count() == slot_count - 1


@pytest.mark.django_db
def test_talk_schedule_api_do_not_delete_slot_with_submission(
    orga_client, event, schedule, slot
):
    with scope(event=event):
        slot = event.wip_schedule.talks.first()
        slot_count = event.wip_schedule.talks.count()
    response = orga_client.delete(
        reverse(
            "orga:schedule.api.update", kwargs={"event": event.slug, "pk": slot.pk}
        ),
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        assert event.wip_schedule.talks.count() == slot_count


@pytest.mark.django_db
def test_talk_schedule_api_delete_bogus_slot(orga_client, event, schedule):
    response = orga_client.delete(
        reverse("orga:schedule.api.update", kwargs={"event": event.slug, "pk": 100}),
        follow=True,
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_talk_schedule_api_update_reset(orga_client, event, schedule, slot, room):
    with scope(event=event):
        slot = event.wip_schedule.talks.first()
        slot.start = now()
        slot.room = room
        slot.save()
        assert slot.start
    response = orga_client.patch(
        reverse(
            "orga:schedule.api.update", kwargs={"event": event.slug, "pk": slot.pk}
        ),
        data=json.dumps({}),
        follow=True,
    )
    with scope(event=event):
        slot.refresh_from_db()
        content = json.loads(response.content.decode())
        assert content["title"] == slot.submission.title
        assert not slot.start
        assert not slot.room


@pytest.mark.django_db
def test_orga_can_quick_schedule_submission(
    orga_client, event, room, accepted_submission
):
    with scope(event=event):
        slot = accepted_submission.slots.get(schedule=event.wip_schedule)
        assert not slot.room
    response = orga_client.get(
        accepted_submission.orga_urls.quick_schedule, follow=True
    )
    assert response.status_code == 200
    response = orga_client.post(
        accepted_submission.orga_urls.quick_schedule,
        data={
            "start_date": event.date_from.strftime("%Y-%m-%d"),
            "start_time": "10:00:00",
            "room": room.pk,
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        slot.refresh_from_db()
        assert slot.room == room, response.content.decode()
        assert slot.start.date() == event.date_from


@pytest.mark.django_db
@pytest.mark.usefixtures("accepted_submission")
@pytest.mark.usefixtures("room")
def test_orga_can_see_schedule(orga_client, event):
    response = orga_client.get(event.orga_urls.schedule, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.usefixtures("accepted_submission")
@pytest.mark.usefixtures("room")
def test_orga_can_see_schedule_release_view(orga_client, event):
    response = orga_client.get(event.orga_urls.release_schedule, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_orga_cannot_reset_to_wrong_version(orga_client, event):
    with scope(event=event):
        assert Schedule.objects.count() == 1
    response = orga_client.get(
        event.orga_urls.reset_schedule, follow=True, data={"version": "Test version 2"}
    )
    assert response.status_code == 200
    with scope(event=event):
        assert Schedule.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.usefixtures("accepted_submission")
@pytest.mark.usefixtures("room")
def test_orga_can_release_and_reset_schedule(orga_client, event):
    with scope(event=event):
        assert Schedule.objects.count() == 1
    response = orga_client.post(
        event.orga_urls.release_schedule,
        follow=True,
        data={"version": "Test version 2"},
    )
    assert response.status_code == 200
    with scope(event=event):
        assert Schedule.objects.count() == 2
    response = orga_client.get(
        event.orga_urls.reset_schedule, follow=True, data={"version": "Test version 2"}
    )
    assert response.status_code == 200
    with scope(event=event):
        assert Schedule.objects.count() == 2


@pytest.mark.django_db
@pytest.mark.usefixtures("accepted_submission")
@pytest.mark.usefixtures("room")
def test_orga_cannot_reuse_schedule_name(orga_client, event):
    with scope(event=event):
        assert Schedule.objects.count() == 1
    response = orga_client.post(
        event.orga_urls.release_schedule,
        follow=True,
        data={"version": "Test version 2"},
    )
    assert response.status_code == 200
    with scope(event=event):
        assert Schedule.objects.count() == 2
        assert Schedule.objects.get(version="Test version 2")
    response = orga_client.post(
        event.orga_urls.release_schedule,
        follow=True,
        data={"version": "Test version 2"},
    )
    assert response.status_code == 200
    with scope(event=event):
        assert Schedule.objects.count() == 2


@pytest.mark.django_db
def test_orga_can_toggle_schedule_visibility(orga_client, event):
    from pretalx.event.models import Event

    assert event.feature_flags["show_schedule"] is True

    response = orga_client.get(event.orga_urls.toggle_schedule, follow=True)
    assert response.status_code == 200
    event = Event.objects.get(pk=event.pk)
    assert event.feature_flags["show_schedule"] is False

    response = orga_client.get(event.orga_urls.toggle_schedule, follow=True)
    assert response.status_code == 200
    event = Event.objects.get(pk=event.pk)
    with scope(event=event):
        assert event.feature_flags["show_schedule"] is True


@pytest.mark.django_db
def test_create_room(orga_client, event, availability):
    with scope(event=event):
        assert event.rooms.count() == 0
    response = orga_client.post(
        event.orga_urls.new_room,
        follow=True,
        data={
            "name_0": "A room",
            "guid": uuid4(),
            "availabilities": json.dumps(
                {
                    "availabilities": [
                        {
                            "start": availability.start.strftime("%Y-%m-%d %H:%M:00Z"),
                            "end": availability.end.strftime("%Y-%m-%d %H:%M:00Z"),
                        }
                    ]
                }
            ),
        },
    )
    assert response.status_code == 200
    with scope(event=event):
        assert event.rooms.count() == 1
        assert str(event.rooms.first().name) == "A room"
        assert event.rooms.first().availabilities.count() == 1
        assert event.rooms.first().availabilities.first().start == availability.start


@pytest.mark.django_db
@pytest.mark.usefixtures("room_availability")
def test_edit_room(orga_client, event, room):
    with scope(event=event):
        assert event.rooms.count() == 1
        assert event.rooms.first().availabilities.count() == 1
        assert str(event.rooms.first().name) != "A room"
    response = orga_client.post(
        room.urls.edit,
        follow=True,
        data={
            "name_0": "A room",
            "guid": uuid4(),
            "availabilities": '{"availabilities": []}',
        },
    )
    assert response.status_code == 200
    with scope(event=event):
        assert event.rooms.count() == 1
        assert str(event.rooms.first().name) == "A room"
        assert event.rooms.first().availabilities.count() == 0


@pytest.mark.django_db
def test_delete_room(orga_client, event, room):
    with scope(event=event):
        assert event.rooms.count() == 1
    response = orga_client.get(room.urls.delete, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert event.rooms.count() == 0


@pytest.mark.django_db
def test_delete_used_room(orga_client, event, room, slot):
    with scope(event=event):
        assert event.rooms.count() == 1
    assert slot.room == room
    response = orga_client.get(room.urls.delete, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert event.rooms.count() == 1


@pytest.mark.django_db
def test_move_rooms_in_list_down(orga_client, room, other_room, event):
    with scope(event=event):
        assert event.rooms.count() == 2
        room.position = 0
        room.save()
        other_room.position = 1
        other_room.save()
    orga_client.post(room.urls.down, follow=True)
    with scope(event=event):
        room.refresh_from_db()
        other_room.refresh_from_db()
        assert room.position == 1
        assert other_room.position == 0


@pytest.mark.django_db
def test_move_rooms_in_list_up(orga_client, room, other_room, event):
    with scope(event=event):
        assert event.rooms.count() == 2
        room.position = 1
        room.save()
        other_room.position = 0
        other_room.save()
    orga_client.post(room.urls.up, follow=True)
    with scope(event=event):
        room.refresh_from_db()
        other_room.refresh_from_db()
        assert room.position == 0
        assert other_room.position == 1


@pytest.mark.django_db
def test_move_rooms_in_list_up_out_of_bounds(orga_client, room, other_room, event):
    with scope(event=event):
        assert event.rooms.count() == 2
        room.position = 0
        room.save()
        other_room.position = 1
        other_room.save()
    orga_client.post(room.urls.up, follow=True)
    with scope(event=event):
        room.refresh_from_db()
        other_room.refresh_from_db()
        assert room.position == 0
        assert other_room.position == 1


@pytest.mark.django_db
def test_move_rooms_in_list_down_out_of_bounds(orga_client, room, other_room, event):
    with scope(event=event):
        assert event.rooms.count() == 2
        room.position = 0
        room.save()
        other_room.position = 1
        other_room.save()
    orga_client.post(other_room.urls.down, follow=True)
    with scope(event=event):
        room.refresh_from_db()
        other_room.refresh_from_db()
        assert room.position == 0
        assert other_room.position == 1


@pytest.mark.django_db
def test_move_rooms_in_list_without_room(orga_client, room, other_room, event):
    with scope(event=event):
        assert event.rooms.count() == 2
        room.position = 0
        room.save()
        other_room.position = 1
        other_room.save()
    orga_client.post(
        other_room.urls.down.replace(str(other_room.pk), str(other_room.pk + 100)),
        follow=True,
    )
    with scope(event=event):
        room.refresh_from_db()
        other_room.refresh_from_db()
        assert room.position == 0
        assert other_room.position == 1


@pytest.mark.django_db
def test_reviewer_cannot_move_rooms_in_list_down(
    review_client, room, other_room, event
):
    with scope(event=event):
        assert event.rooms.count() == 2
        room.position = 0
        room.save()
        other_room.position = 1
        other_room.save()
    review_client.post(room.urls.down, follow=True)
    with scope(event=event):
        room.refresh_from_db()
        other_room.refresh_from_db()
        assert room.position == 0
        assert other_room.position == 1


@pytest.mark.django_db
def test_regenerate_speaker_notifications(orga_client, event, slot):
    with scope(event=event):
        queue_count = event.queued_mails.count()
    response = orga_client.post(
        event.orga_urls.schedule + "resend_mails",
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        assert event.queued_mails.count() > queue_count
        mail = event.queued_mails.last()
        assert slot.submission.title in mail.text
        assert str(slot.room.name) in mail.text


@pytest.mark.django_db
def test_regenerate_speaker_notifications_before_schedule(orga_client, event):
    with scope(event=event):
        queue_count = event.queued_mails.count()
    response = orga_client.post(
        event.orga_urls.schedule + "resend_mails",
        follow=True,
    )
    assert response.status_code == 200
    assert (
        "You can only regenerate mails after the first schedule was released."
        in response.content.decode()
    )
    with scope(event=event):
        assert event.queued_mails.count() == queue_count


@pytest.mark.django_db
def test_orga_cant_export_answers_csv_empty(orga_client, speaker, event, submission):
    response = orga_client.post(
        event.orga_urls.schedule_export,
        data={
            "target": "rejected",
            "title": "on",
            "export_format": "csv",
        },
    )
    assert response.status_code == 200
    assert (
        response.content.decode().strip().startswith("<!DOCTYPE")
    )  # HTML response instead of empty download


@pytest.mark.django_db
def test_orga_cant_export_answers_csv_without_delimiter(
    orga_client, speaker, event, submission, answered_choice_question
):
    with scope(event=event):
        answered_choice_question.target = "submission"
        answered_choice_question.save()
    response = orga_client.post(
        event.orga_urls.schedule_export,
        data={
            "target": "all",
            "title": "on",
            f"question_{answered_choice_question.id}": "on",
            "export_format": "csv",
        },
    )
    assert response.status_code == 200
    assert response.content.decode().strip().startswith("<!DOCTYPE")


@pytest.mark.django_db
def test_orga_can_export_answers_csv(
    orga_client, speaker, event, submission, answered_choice_question
):
    with scope(event=event):
        answered_choice_question.target = "submission"
        answered_choice_question.save()
        answer = answered_choice_question.answers.all().first().answer_string
    response = orga_client.post(
        event.orga_urls.schedule_export,
        data={
            "target": "all",
            "title": "on",
            f"question_{answered_choice_question.id}": "on",
            "speaker_ids": "on",
            "export_format": "csv",
            "data_delimiter": "comma",
        },
    )
    assert response.status_code == 200
    assert (
        response.content.decode()
        == f"ID,Proposal title,Speaker IDs,{answered_choice_question.question}\r\n{submission.code},{submission.title},{speaker.code},{answer}\r\n"
    )


@pytest.mark.django_db
def test_orga_can_export_answers_json(
    orga_client, speaker, event, submission, answered_choice_question
):
    with scope(event=event):
        answered_choice_question.target = "submission"
        answered_choice_question.save()
        answer = answered_choice_question.answers.all().first().answer_string
    response = orga_client.post(
        event.orga_urls.schedule_export,
        data={
            "target": "all",
            "title": "on",
            f"question_{answered_choice_question.id}": "on",
            "speaker_ids": "on",
            "export_format": "json",
        },
    )
    assert response.status_code == 200
    assert json.loads(response.content.decode()) == [
        {
            "ID": submission.code,
            "Proposal title": submission.title,
            answered_choice_question.question: answer,
            "Speaker IDs": [speaker.code],
        }
    ]
