import json

import pytest
from django_scopes import scope

from pretalx.schedule.models import Schedule


@pytest.fixture
def invisible_slot(past_slot):
    past_slot.is_visible = False
    past_slot.save()
    return past_slot


@pytest.mark.django_db
def test_user_can_see_schedule(client, slot, event):
    with scope(event=event):
        assert slot.submission.event.schedules.count() == 2
    response = client.get(slot.submission.event.api_urls.schedules, follow=True)
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["count"] == 1


@pytest.mark.django_db
def test_user_cannot_see_wip_schedule_list(client, slot, event):
    with scope(event=event):
        assert slot.submission.event.schedules.count() == 2
    response = client.get(slot.submission.event.api_urls.schedules, follow=True)
    content = json.loads(response.text)
    assert response.status_code == 200
    assert content["count"] == 1
    for schedule_data in content["results"]:
        assert schedule_data["version"] is not None


@pytest.mark.django_db
def test_user_cannot_see_schedule_if_not_public(client, slot, event):
    slot.submission.event.feature_flags["show_schedule"] = False
    slot.submission.event.save()
    with scope(event=event):
        assert slot.submission.event.schedules.count() == 2
    response = client.get(slot.submission.event.api_urls.schedules, follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_orga_can_see_schedule(client, orga_user_token, slot, event):
    with scope(event=event):
        assert slot.submission.event.schedules.count() == 2
    response = client.get(
        slot.submission.event.api_urls.schedules,
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["count"] == 2


@pytest.mark.django_db
def test_orga_cannot_see_schedule_even_if_not_public(
    client, orga_user_token, slot, event
):
    slot.submission.event.feature_flags["show_schedule"] = False
    slot.submission.event.save()
    with scope(event=event):
        assert slot.submission.event.schedules.count() == 2
    response = client.get(
        slot.submission.event.api_urls.schedules,
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["count"] == 2


@pytest.mark.django_db
def test_orga_can_access_wip_schedule_shortcut(client, orga_user_token, event, slot):
    with scope(event=event):
        wip_schedule = event.wip_schedule
        assert wip_schedule is not None
        wip_schedule.talks.add(slot)

    response = client.get(
        event.api_urls.schedules + "wip/",
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["version"] == event.wip_schedule.version_with_fallback


@pytest.mark.django_db
def test_user_cannot_access_wip_schedule_shortcut(client, event, slot):
    response = client.get(event.api_urls.schedules + "wip/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_orga_can_access_latest_schedule_shortcut(
    client, orga_user_token, event, slot, break_slot
):
    with scope(event=event):
        assert event.current_schedule is not None
        current_schedule_version = event.current_schedule.version

    response = client.get(
        event.api_urls.schedules + "latest/",
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["version"] == current_schedule_version
    assert len(content["slots"]) == 2


@pytest.mark.django_db
def test_user_can_access_latest_schedule_shortcut_if_public(client, event, slot):
    with scope(event=event):
        assert event.current_schedule is not None
        event.is_public = True
        event.feature_flags["show_schedule"] = True
        event.save()
        current_schedule_version = event.current_schedule.version

    response = client.get(event.api_urls.schedules + "latest/")
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["version"] == current_schedule_version


@pytest.mark.django_db
def test_user_cannot_access_latest_schedule_shortcut_if_schedule_not_public(
    client, event, slot
):
    with scope(event=event):
        assert event.current_schedule is not None
        event.is_public = True
        event.feature_flags["show_schedule"] = False
        event.save()

    response = client.get(event.api_urls.schedules + "latest/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_user_cannot_access_latest_schedule_shortcut_if_event_not_public(
    client, event, slot
):
    with scope(event=event):
        assert event.current_schedule is not None
        event.is_public = False
        event.save()
    response = client.get(event.api_urls.schedules + "latest/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_latest_schedule_shortcut_404_if_no_current_schedule(
    client, orga_user_token, event
):
    with scope(event=event):
        Schedule.objects.filter(event=event).delete()
        event.current_schedule = None
        event.save()
        event.schedules.create(version=None)

    response = client.get(
        event.api_urls.schedules + "latest/",
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_redirect_version_success(client, event):
    with scope(event=event):
        schedule = event.wip_schedule
        schedule.freeze("v2.0")
    response = client.get(event.api_urls.schedules + "by-version/?version=v2.0")
    assert response.status_code == 302
    assert response["Location"].endswith(f"/schedules/{schedule.pk}/")


@pytest.mark.django_db
def test_redirect_version_nonexistent_version(client, event):
    response = client.get(
        event.api_urls.schedules + "by-version/?version=nonexistent_version_name"
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_redirect_version_missing_query_param(client, event):
    response = client.get(event.api_urls.schedules + "by-version/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_redirect_version_followed_by_user_schedule_not_public(client, event):
    with scope(event=event):
        event.feature_flags["show_schedule"] = False
        event.save()
        schedule = event.wip_schedule
        schedule.freeze("v2.0")

    response = client.get(
        event.api_urls.schedules + "by-version/?version=v2.0", follow=True
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_orga_can_release_schedule(client, orga_user_write_token, event, slot):
    with scope(event=event):
        initial_wip_schedule = event.wip_schedule
        assert initial_wip_schedule.version is None
        initial_wip_pk = initial_wip_schedule.pk
        initial_schedule_count = event.schedules.count()

    release_data = {"version": "v_test_release", "comment": "A test release comment"}
    response = client.post(
        event.api_urls.schedules + "release/",
        data=json.dumps(release_data),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 201, response.text
    content = json.loads(response.text)

    with scope(event=event):
        assert content["version"] == release_data["version"]
        assert content["comment"]["en"] == release_data["comment"]

        released_schedule = event.schedules.get(version=release_data["version"])
        assert released_schedule.pk == initial_wip_pk
        assert released_schedule.comment == release_data["comment"]

        del event.wip_schedule
        new_wip_schedule = event.wip_schedule
        assert new_wip_schedule.pk != initial_wip_pk
        assert new_wip_schedule.version is None
        assert event.schedules.count() == initial_schedule_count + 1


@pytest.mark.django_db
def test_orga_cannot_release_schedule_with_existing_version(
    client, orga_user_write_token, event
):
    with scope(event=event):
        event.wip_schedule.freeze("v2.0")
    release_data = {"version": "v2.0"}
    response = client.post(
        event.api_urls.schedules + "release/",
        data=json.dumps(release_data),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 400
    content = json.loads(response.text)
    assert "version" in content


@pytest.mark.django_db
def test_orga_cannot_release_schedule_without_version_name(
    client, orga_user_write_token, event
):
    release_data = {"comment": "Just a comment"}
    response = client.post(
        event.api_urls.schedules + "release/",
        data=json.dumps(release_data),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 400
    content = json.loads(response.text)
    assert "version" in content


@pytest.mark.django_db
def test_anonymous_user_cannot_release_schedule(client, event):
    release_data = {"version": "v_anon_release"}
    response = client.post(
        event.api_urls.schedules + "release/",
        data=json.dumps(release_data),
        content_type="application/json",
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_orga_readonly_user_cannot_release_schedule(client, orga_user_token, event):
    release_data = {"version": "v_readonly_release"}
    response = client.post(
        event.api_urls.schedules + "release/",
        data=json.dumps(release_data),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_user_can_download_slot_ical(client, slot, event):
    url = event.api_urls.slots + f"{slot.pk}/ical/"
    response = client.get(url, follow=True)

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "text/calendar"
    expected_filename = (
        f'attachment; filename="{event.slug}-{slot.submission.code}.ics"'
    )
    assert response.headers["Content-Disposition"] == expected_filename
    content = response.text
    assert "BEGIN:VCALENDAR" in content
    assert f"{slot.submission.code}" in content


@pytest.mark.django_db
def test_user_cannot_download_slot_ical_if_slot_not_visible(client, slot, event):
    with scope(event=event):
        slot.is_visible = False
        slot.save()

    url = event.api_urls.slots + f"{slot.pk}/ical/"
    response = client.get(url, follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_user_cannot_download_slot_ical_if_schedule_not_public(client, slot, event):
    with scope(event=event):
        event.feature_flags["show_schedule"] = False
        event.save()

    url = event.api_urls.slots + f"{slot.pk}/ical/"
    response = client.get(url, follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_user_cannot_download_slot_ical_if_event_not_public(client, slot, event):
    with scope(event=event):
        event.is_public = False
        event.save()

    url = event.api_urls.slots + f"{slot.pk}/ical/"
    response = client.get(url, follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_download_slot_ical_slot_without_submission(client, event, break_slot):
    with scope(event=event):
        assert break_slot.schedule == event.current_schedule
    url = event.api_urls.slots + f"{break_slot.pk}/ical/"
    response = client.get(url, follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_list_slots_anonymous_event_not_public(client, event, slot):
    event.is_public = False
    event.save()
    response = client.get(event.api_urls.slots, follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_list_slots_anonymous_schedule_not_public(client, event, slot):
    event.is_public = True
    event.feature_flags["show_schedule"] = False
    event.save()
    response = client.get(event.api_urls.slots, follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_list_slots_anonymous_schedule_public_current_schedule_only(
    client, event, slot
):
    with scope(event=event):
        code = slot.submission.code
    response = client.get(event.api_urls.slots, follow=True)
    content = json.loads(response.text)
    assert response.status_code == 200
    assert content["count"] == 1
    assert content["results"][0]["id"] == slot.pk
    assert "is_visible" not in content["results"][0]
    assert content["results"][0]["submission"] == code


@pytest.mark.django_db
def test_list_slots_anonymous_schedule_public_only_visible(
    client, event, slot, invisible_slot
):
    with scope(event=event):
        slot_pk = event.current_schedule.talks.get(submission=slot.submission).pk
    response = client.get(event.api_urls.slots, follow=True)
    content = json.loads(response.text)
    assert response.status_code == 200
    assert content["count"] == 1
    assert content["results"][0]["id"] == slot_pk


@pytest.mark.django_db
def test_list_slots_orga_sees_slots_in_current_schedule_by_default(
    client, orga_user_token, event, slot, invisible_slot
):
    with scope(event=event):
        wip_slot = event.wip_schedule.talks.first()
        current_schedule_slot_ids = set(
            event.current_schedule.talks.values_list("pk", flat=True)
        )

    response = client.get(
        event.api_urls.slots,
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)
    assert response.status_code == 200

    assert content["count"] == len(current_schedule_slot_ids)

    slot_ids_in_response = {r["id"] for r in content["results"]}
    assert slot.pk in slot_ids_in_response
    assert invisible_slot.pk in slot_ids_in_response
    assert wip_slot.pk not in slot_ids_in_response


@pytest.mark.django_db
def test_list_slots_orga_can_filter_by_schedule_pk(
    client, orga_user_token, event, slot
):
    with scope(event=event):
        event.wip_schedule.freeze("v2.0")
        current_schedule_id = slot.schedule.pk
        code = slot.submission.code

    response = client.get(
        f"{event.api_urls.slots}?schedule={current_schedule_id}",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)
    assert response.status_code == 200, content
    assert content["count"] >= 1
    assert slot.pk in [s["id"] for s in content["results"]]

    response = client.get(
        f"{event.api_urls.slots}?submission={code}",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)
    assert response.status_code == 200
    assert content["count"] == 3


@pytest.mark.django_db
def test_retrieve_slot_anonymous_not_visible(client, event, invisible_slot):
    response = client.get(event.api_urls.slots + f"{invisible_slot.pk}/", follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_retrieve_slot_anonymous_visible_schedule_public(client, event, slot):
    with scope(event=event):
        code = slot.submission.code
    response = client.get(event.api_urls.slots + f"{slot.pk}/", follow=True)
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["id"] == slot.pk
    assert "is_visible" not in content
    assert content["submission"] == code


@pytest.mark.django_db
def test_retrieve_slot_anonymous_schedule_not_public(client, event, slot):
    with scope(event=event):
        event.is_public = True
        event.feature_flags["show_schedule"] = False
        event.save()
    response = client.get(event.api_urls.slots + f"{slot.pk}/", follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_retrieve_slot_orga_can_see_invisible_slot(
    client, orga_user_token, event, invisible_slot
):
    response = client.get(
        event.api_urls.slots + f"{invisible_slot.pk}/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["id"] == invisible_slot.pk


@pytest.mark.django_db
def test_retrieve_slot_without_submission_orga(
    client, orga_user_token, event, room, break_slot
):
    url = event.api_urls.slots + f"{break_slot.pk}/"
    response = client.get(
        url,
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )

    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["id"] == break_slot.pk
    assert content["submission"] is None
    assert content["room"] == room.pk


@pytest.mark.django_db
def test_retrieve_slot_without_submission(client, event, room, break_slot):
    with scope(event=event):
        assert break_slot.schedule == event.current_schedule

    url = event.api_urls.slots + f"{break_slot.pk}/"
    response = client.get(url, follow=True)

    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["id"] == break_slot.pk
    assert content["submission"] is None
    assert content["room"] == room.pk


@pytest.mark.django_db
def test_retrieve_slot_nonexistent(client, event, slot):
    response = client.get(event.api_urls.slots + "99999/", follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_update_slot_anonymous(client, event, slot):
    response = client.patch(
        event.api_urls.slots + f"{slot.pk}/",
        data=json.dumps({"is_visible": False}),
        content_type="application/json",
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_update_slot_orga_readonly_token(client, event, slot, orga_user_token):
    with scope(event=event):
        wip_slot = event.wip_schedule.talks.filter(submission=slot.submission).first()

    response = client.patch(
        event.api_urls.slots + f"{wip_slot.pk}/",
        data=json.dumps({"room": None}),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 403
    with scope(event=event):
        wip_slot.refresh_from_db()
        assert wip_slot.room is not None


@pytest.mark.django_db
def test_update_slot_orga_write_token_cannot_change_visibility(
    client, event, slot, orga_user_write_token
):
    with scope(event=event):
        wip_slot = event.wip_schedule.talks.filter(submission=slot.submission).first()
    initial_visibility = wip_slot.is_visible
    response = client.patch(
        event.api_urls.slots + f"{wip_slot.pk}/",
        data=json.dumps({"is_visible": not initial_visibility}),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["is_visible"] == initial_visibility
    with scope(event=event):
        wip_slot.refresh_from_db()
        assert wip_slot.is_visible == initial_visibility


@pytest.mark.django_db
def test_update_slot_orga_write_token_change_room(
    client, event, slot, orga_user_write_token, room, other_room
):
    with scope(event=event):
        wip_slot = event.wip_schedule.talks.filter(submission=slot.submission).first()
        assert wip_slot.room == room
    response = client.patch(
        event.api_urls.slots + f"{wip_slot.pk}/",
        data=json.dumps({"room": other_room.pk}),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 200
    with scope(event=event):
        wip_slot.refresh_from_db()
        assert wip_slot.room == other_room


@pytest.mark.django_db
def test_update_slot_orga_write_token_clear_room(
    client, event, slot, orga_user_write_token, room
):
    with scope(event=event):
        wip_slot = event.wip_schedule.talks.filter(submission=slot.submission).first()
        assert wip_slot.room == room
    response = client.patch(
        event.api_urls.slots + f"{wip_slot.pk}/",
        data=json.dumps({"room": None}),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 200
    with scope(event=event):
        wip_slot.refresh_from_db()
        assert wip_slot.room is None


@pytest.mark.django_db
def test_update_slot_orga_write_token_change_room_non_wip(
    client, event, slot, other_room, orga_user_write_token
):
    assert slot.schedule.version is not None
    assert slot.room != other_room
    response = client.patch(
        event.api_urls.slots + f"{slot.pk}/",
        data=json.dumps({"room": other_room.pk}),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 403


@pytest.mark.parametrize("has_submission", (True, False))
@pytest.mark.django_db
def test_update_slot_orga_write_submission_fields(
    client, event, slot, other_room, orga_user_write_token, has_submission
):
    with scope(event=event):
        wip_slot = event.wip_schedule.talks.filter(submission=slot.submission).first()
        if not has_submission:
            wip_slot.submission = None
            wip_slot.save()
    response = client.patch(
        event.api_urls.slots + f"{wip_slot.pk}/",
        data=json.dumps({"description": "test", "end": wip_slot.end.isoformat()}),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    content = json.loads(response.text)
    if has_submission:
        assert response.status_code == 400
        assert "end" in content
        assert "description" in content
    else:
        assert content["description"]["en"] == "test"


@pytest.mark.django_db
def test_talk_slot_expand_parameters(client, orga_user_token, event, slot):
    url = event.api_urls.slots + f"{slot.pk}/"
    base_headers = {"Authorization": f"Token {orga_user_token.token}"}

    with scope(event=event):
        submission_code = slot.submission.code
        room_pk = slot.room.pk
        speaker = slot.submission.speakers.first().code

    response = client.get(url, headers=base_headers)
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["submission"] == submission_code
    assert content["room"] == room_pk
    assert content["schedule"] == slot.schedule_id

    response = client.get(
        url + "?expand=room,schedule,submission,submission.speakers",
        headers=base_headers,
    )
    assert response.status_code == 200
    content = json.loads(response.text)

    assert isinstance(content["room"], dict)
    assert content["room"]["id"] == room_pk
    assert content["room"]["name"]["en"] == slot.room.name

    assert isinstance(content["submission"], dict)
    assert content["submission"]["code"] == submission_code
    assert isinstance(content["submission"]["speakers"], list)

    assert isinstance(content["submission"]["speakers"], list)
    speaker_data = content["submission"]["speakers"][0]
    assert speaker_data["code"] == speaker


@pytest.mark.django_db
def test_schedule_expand_slots(client, event, slot, track):
    with scope(event=event):
        submission = slot.submission
        room = slot.room
        speaker = slot.submission.speakers.first()
        submission_type = slot.submission.submission_type
        slot.submission.track = track
        slot.submission.save()
        profile = speaker.event_profile(event)
        event.feature_flags["use_tracks"] = True
        event.save()
    response = client.get(
        event.api_urls.schedules
        + "latest/?expand=slots.room,slots.submission.speakers,slots.submission.track,slots.submission.submission_type",
        follow=True,
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert isinstance(content["slots"], list)
    assert len(content["slots"]) > 0
    assert all(isinstance(s, dict) for s in content["slots"])
    expanded_slot = [s for s in content["slots"] if s["id"] == slot.pk][0]
    assert expanded_slot is not None
    assert "start" in expanded_slot
    assert "end" in expanded_slot
    assert expanded_slot["room"]["id"] == room.id
    assert expanded_slot["room"]["name"]["en"] == room.name
    submission_content = expanded_slot["submission"]
    assert submission_content["code"] == submission.code
    assert submission_content["title"] == submission.title
    assert submission_content["track"]["name"]["en"] == track.name
    assert submission_content["submission_type"]["name"]["en"] == submission_type.name
    assert isinstance(submission_content["speakers"], list)
    speaker_data = submission_content["speakers"][0]
    assert speaker_data["code"] == speaker.code
    assert speaker_data["name"] == speaker.name
    assert speaker_data["biography"] == profile.biography
