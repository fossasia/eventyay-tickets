import json

import pytest
from django_scopes import scope

from pretalx.api.serializers.review import ReviewSerializer


@pytest.mark.django_db
def test_review_serializer(review):
    with scope(event=review.event):
        data = ReviewSerializer(review).data
        assert set(data.keys()) == {
            "id",
            "answers",
            "submission",
            "user",
            "text",
            "score",
            "override_vote",
            "created",
            "updated",
        }
        assert data["submission"] == review.submission.code
        assert data["user"] == review.user.name
        assert data["answers"] == []


@pytest.mark.django_db
def test_anon_cannot_see_reviews(client, event, review):
    response = client.get(event.api_urls.reviews, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert len(content["results"]) == 0, content


@pytest.mark.django_db
def test_orga_can_see_reviews(orga_client, event, review):
    response = orga_client.get(event.api_urls.reviews, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert len(content["results"]) == 1


@pytest.mark.django_db
def test_orga_cannot_see_reviews_of_deleted_submission(orga_client, event, review):
    review.submission.state = "deleted"
    review.submission.save()
    response = orga_client.get(event.api_urls.reviews, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert len(content["results"]) == 0


@pytest.mark.django_db
def test_reviewer_can_see_reviews(review_client, event, review, other_review):
    response = review_client.get(event.api_urls.reviews, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert len(content["results"]) == 2, content


@pytest.mark.django_db
def test_reviewer_can_see_reviews_by_track(
    review_client, review_user, event, review, other_review, track, other_track
):
    review.submission.track = track
    review.submission.save()
    other_review.submission.track = other_track
    other_review.submission.save()
    review_user.teams.filter(is_reviewer=True).first().limit_tracks.add(track)

    response = review_client.get(event.api_urls.reviews, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert len(content["results"]) == 1, content


@pytest.mark.django_db
def test_reviewer_can_filter_by_submission(review_client, event, review, other_review):
    response = review_client.get(
        event.api_urls.reviews + f"?submission__code={review.submission.code}",
        follow=True,
    )
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert len(content["results"]) == 1, content


@pytest.mark.django_db
def test_reviewer_cannot_see_review_to_own_talk(
    review_user, review_client, event, review, other_review
):
    other_review.submission.speakers.add(review_user)
    response = review_client.get(event.api_urls.reviews, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert len(content["results"]) == 1, content
