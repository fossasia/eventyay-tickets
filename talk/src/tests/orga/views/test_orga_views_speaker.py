import json

import pytest
from django_scopes import scope, scopes_disabled

from pretalx.submission.models.question import QuestionRequired


@pytest.mark.django_db
@pytest.mark.parametrize("query", ("", "?role=true", "?role=false", "?role=foobar"))
def test_orga_can_access_speakers_list(orga_client, speaker, event, submission, query):
    response = orga_client.get(event.orga_urls.speakers + query, follow=True)
    assert response.status_code == 200
    if not query:
        assert speaker.name in response.content.decode()


@pytest.mark.django_db
def test_orga_can_access_speaker_page(orga_client, speaker, event, submission):
    with scope(event=event):
        url = speaker.event_profile(event).orga_urls.base
    response = orga_client.get(url, follow=True)
    assert response.status_code == 200
    assert speaker.name in response.content.decode()


@pytest.mark.django_db
def test_orga_can_change_speaker_password(orga_client, speaker, event, submission):
    with scope(event=event):
        url = speaker.event_profile(event).orga_urls.password_reset
        assert not speaker.pw_reset_token
    response = orga_client.get(url, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        speaker.refresh_from_db()
        assert not speaker.pw_reset_token
    response = orga_client.post(url, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        speaker.refresh_from_db()
        assert speaker.pw_reset_token


@pytest.mark.django_db
def test_reviewer_can_access_speaker_page(review_client, speaker, event, submission):
    with scope(event=event):
        url = speaker.event_profile(event).orga_urls.base
    response = review_client.get(url, follow=True)
    assert response.status_code == 200
    assert speaker.name in response.content.decode()


@pytest.mark.django_db
def test_reviewer_cannot_change_speaker_password(
    review_client, speaker, event, submission
):
    assert not speaker.pw_reset_token
    with scope(event=event):
        url = speaker.event_profile(event).orga_urls.password_reset
    response = review_client.post(url, follow=True)
    assert response.status_code == 404
    with scope(event=event):
        speaker.refresh_from_db()
        assert not speaker.pw_reset_token


@pytest.mark.django_db
def test_reviewer_cannot_access_speaker_page_with_deleted_submission(
    review_client, other_speaker, event, deleted_submission
):
    with scope(event=event):
        assert event.submissions.all().count() == 0
        assert event.submissions(manager="all_objects").count() == 1
        url = other_speaker.event_profile(event).orga_urls.base
    response = review_client.get(url, follow=True)
    assert response.status_code == 404
    assert other_speaker.name not in response.content.decode()


@pytest.mark.django_db
def test_orga_can_edit_speaker(orga_client, speaker, event, submission):
    with scope(event=event):
        url = speaker.event_profile(event).orga_urls.base
        profile = speaker.event_profile(event)
        count = profile.logged_actions().all().count()
    response = orga_client.post(
        url,
        data={
            "name": "BESTSPEAKAR",
            "biography": "I rule!",
            "email": "foo@foooobar.de",
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        speaker.refresh_from_db()
        assert count + 1 == profile.logged_actions().all().count()
    assert speaker.name == "BESTSPEAKAR", response.content.decode()
    assert speaker.email == "foo@foooobar.de"


@pytest.mark.django_db
def test_orga_can_edit_speaker_unchanged(orga_client, speaker, event, submission):
    with scope(event=event):
        url = speaker.event_profile(event).orga_urls.base
        profile = speaker.event_profile(event)
        count = profile.logged_actions().all().count()
        event.cfp.fields["availabilities"]["visibility"] = "do_not_ask"
        event.cfp.save()
    response = orga_client.post(
        url,
        data={
            "name": speaker.name,
            "biography": profile.biography,
            "email": speaker.email,
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        speaker.refresh_from_db()
        assert count == profile.logged_actions().all().count()


@pytest.mark.django_db
def test_orga_cannot_edit_speaker_without_filling_questions(
    orga_client, speaker, event, submission, speaker_question
):
    with scope(event=event):
        url = speaker.event_profile(event).orga_urls.base
        speaker_question.question_required = QuestionRequired.REQUIRED
        speaker_question.save()
    response = orga_client.post(
        url,
        data={
            "name": "BESTSPEAKAR",
            "biography": "bio",
            "email": speaker.email,
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        speaker.refresh_from_db()
    assert speaker.name == "BESTSPEAKAR", response.content.decode()


@pytest.mark.django_db
def test_orga_cant_assign_duplicate_address(
    orga_client, speaker, event, submission, other_speaker
):
    event.cfp.fields["availabilities"]["visibility"] = "do_not_ask"
    event.cfp.save()
    with scope(event=event):
        url = speaker.event_profile(event).orga_urls.base
    response = orga_client.post(
        url,
        data={
            "name": "BESTSPEAKAR",
            "biography": "I rule!",
            "email": other_speaker.email,
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        speaker.refresh_from_db()
    assert speaker.name != "BESTSPEAKAR", response.content.decode()
    assert speaker.email != other_speaker.email


@pytest.mark.django_db
def test_orga_can_edit_speaker_status(orga_client, speaker, event, submission):
    with scopes_disabled():
        logs = speaker.logged_actions().count()
    with scope(event=event):
        assert speaker.profiles.first().has_arrived is False
        url = speaker.profiles.first().orga_urls.toggle_arrived
    response = orga_client.get(url, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        speaker.refresh_from_db()
        assert speaker.profiles.first().has_arrived is True
    with scopes_disabled():
        assert speaker.logged_actions().count() == logs + 1
    response = orga_client.get(url + "?from=list", follow=True)
    assert response.status_code == 200
    with scope(event=event):
        speaker.refresh_from_db()
        assert speaker.profiles.first().has_arrived is False
    with scopes_disabled():
        assert speaker.logged_actions().count() == logs + 2


@pytest.mark.django_db
def test_reviewer_cannot_edit_speaker(review_client, speaker, event, submission):
    with scope(event=event):
        url = speaker.event_profile(event).orga_urls.base
    response = review_client.post(
        url,
        data={"name": "BESTSPEAKAR", "biography": "I rule!"},
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        speaker.refresh_from_db()
    assert speaker.name != "BESTSPEAKAR", response.content.decode()


@pytest.mark.django_db
def test_orga_can_create_speaker_information(orga_client, event):
    with scope(event=event):
        assert event.information.all().count() == 0
    orga_client.post(
        event.orga_urls.new_information,
        data={
            "title_0": "Test Information",
            "text_0": "Very Important!!!",
            "target_group": "submitters",
        },
        follow=True,
    )
    with scope(event=event):
        assert event.information.all().count() == 1


@pytest.mark.django_db
def test_orga_can_edit_speaker_information(orga_client, event, information):
    orga_client.post(
        information.orga_urls.edit,
        data={
            "title_0": "Banana banana",
            "text_0": "Very Important!!!",
            "target_group": "submitters",
        },
        follow=True,
    )
    with scope(event=event):
        information.refresh_from_db()
        assert str(information.title) == "Banana banana"


@pytest.mark.django_db
def test_reviewer_cant_edit_speaker_information(review_client, event, information):
    review_client.post(
        information.orga_urls.edit,
        data={
            "title_0": "Banana banana",
            "text_0": "Very Important!!!",
            "target_group": "confirmed",
        },
        follow=True,
    )
    with scope(event=event):
        information.refresh_from_db()
        assert str(information.title) != "Banana banana"


@pytest.mark.django_db
def test_orga_can_delete_speaker_information(orga_client, event, information):
    with scope(event=event):
        assert event.information.all().count() == 1
    orga_client.post(information.orga_urls.delete, follow=True)
    with scope(event=event):
        assert event.information.all().count() == 0


@pytest.mark.django_db
def test_orga_cant_export_answers_csv_empty(orga_client, speaker, event, submission):
    response = orga_client.post(
        event.orga_urls.speakers + "export/",
        data={
            "target": "rejected",
            "name": "on",
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
        answered_choice_question.target = "speaker"
        answered_choice_question.save()
    response = orga_client.post(
        event.orga_urls.speakers + "export/",
        data={
            "target": "all",
            "name": "on",
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
        answered_choice_question.target = "speaker"
        answered_choice_question.save()
        answer = answered_choice_question.answers.all().first().answer_string
    response = orga_client.post(
        event.orga_urls.speakers + "export/",
        data={
            "target": "all",
            "name": "on",
            f"question_{answered_choice_question.id}": "on",
            "submission_ids": "on",
            "export_format": "csv",
            "data_delimiter": "comma",
        },
    )
    assert response.status_code == 200
    assert (
        response.content.decode()
        == f"ID,Name,Proposal IDs,{answered_choice_question.question}\r\n{speaker.code},{speaker.name},{submission.code},{answer}\r\n"
    )


@pytest.mark.django_db
def test_orga_can_export_answers_json(
    orga_client, speaker, event, submission, answered_choice_question
):
    with scope(event=event):
        answered_choice_question.target = "speaker"
        answered_choice_question.save()
        answer = answered_choice_question.answers.all().first().answer_string
    response = orga_client.post(
        event.orga_urls.speakers + "export/",
        data={
            "target": "all",
            "name": "on",
            f"question_{answered_choice_question.id}": "on",
            "submission_ids": "on",
            "export_format": "json",
        },
    )
    assert response.status_code == 200
    assert json.loads(response.content.decode()) == [
        {
            "ID": speaker.code,
            "Name": speaker.name,
            answered_choice_question.question: answer,
            "Proposal IDs": [submission.code],
        }
    ]
