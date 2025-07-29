import json
from decimal import Decimal

import pytest
from django_scopes import scope

from pretalx.api.serializers.review import ReviewSerializer
from pretalx.submission.models import Answer, Review, ReviewScore, ReviewScoreCategory


@pytest.fixture
def review_score_category(event):
    return ReviewScoreCategory.objects.create(event=event, name="Impact", weight=1)


@pytest.fixture
def review_score_value_positive(review_score_category):
    return ReviewScore.objects.create(
        category=review_score_category, value=Decimal("2.0"), label="Good"
    )


@pytest.fixture
def review_score_value_negative(review_score_category):
    return ReviewScore.objects.create(
        category=review_score_category, value=Decimal("-1.0"), label="Bad"
    )


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
            "scores",
        }
        assert data["submission"] == review.submission.code
        assert data["user"] == review.user.code
        assert data["answers"] == []


@pytest.mark.django_db
def test_anon_cannot_see_reviews(client, event, review):
    response = client.get(event.api_urls.reviews, follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_orga_can_see_reviews(client, orga_user_token, event, review):
    response = client.get(
        event.api_urls.reviews + "?expand=answers",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert len(content["results"]) == 1


@pytest.mark.django_db
def test_orga_can_see_expanded_reviews(
    client,
    orga_user_token,
    event,
    review,
    track,
    review_score_value_positive,
    review_question,
):
    with scope(event=event):
        review.submission.track = track
        review.scores.add(review_score_value_positive)
        review.submission.save()
        speaker = review.submission.speakers.all().first()
        submission_type = review.submission.submission_type
        user = review.user
        category = review_score_value_positive.category
        Answer.objects.create(review=review, question=review_question, answer="text!")

    params = ",".join(
        [
            "user",
            "scores.category",
            "submission.speakers",
            "submission.track",
            "submission.submission_type",
            "answers",
        ]
    )
    response = client.get(
        f"{event.api_urls.reviews}?expand={params}",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert len(content["results"]) == 1
    data = content["results"][0]
    assert data["submission"]["code"] == review.submission.code
    assert data["submission"]["speakers"][0]["code"] == speaker.code
    assert data["submission"]["track"]["name"]["en"] == track.name
    assert data["submission"]["submission_type"]["name"]["en"] == submission_type.name
    assert data["user"]["code"] == user.code
    assert data["scores"][0]["category"]["name"]["en"] == category.name
    assert data["answers"][0]["answer"] == "text!"


@pytest.mark.django_db
def test_orga_cannot_see_reviews_of_deleted_submission(
    client, orga_user_token, event, review
):
    review.submission.state = "deleted"
    review.submission.save()
    response = client.get(
        event.api_urls.reviews,
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert len(content["results"]) == 0


@pytest.mark.django_db
def test_reviewer_can_see_reviews(
    client, review_user_token, event, review, other_review
):
    with scope(event=event):
        event.active_review_phase.can_see_other_reviews = "always"
        event.active_review_phase.save()
    response = client.get(
        event.api_urls.reviews,
        follow=True,
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200, content
    assert len(content["results"]) == 2, content


@pytest.mark.django_db
def test_reviewer_can_see_reviews_by_track(
    client,
    review_user_token,
    review_user,
    event,
    review,
    other_review,
    track,
    other_track,
    slot,  # Make sure this also applies once there is a public schedule!
):
    with scope(event=event):
        event.active_review_phase.can_see_other_reviews = "always"
        event.active_review_phase.save()
        review.submission.track = track
        review.submission.save()
        other_review.submission.track = other_track
        other_review.submission.save()
        review_user.teams.filter(is_reviewer=True).first().limit_tracks.add(track)

    response = client.get(
        event.api_urls.reviews,
        follow=True,
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert len(content["results"]) == 1, content


@pytest.mark.django_db
def test_reviewer_can_filter_by_submission(
    client, review_user_token, event, review, other_review
):
    with scope(event=event):
        event.active_review_phase.can_see_other_reviews = "always"
        event.active_review_phase.save()
    response = client.get(
        event.api_urls.reviews + f"?submission={review.submission.code}",
        follow=True,
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert len(content["results"]) == 1, content


@pytest.mark.django_db
def test_reviewer_cannot_see_review_to_own_talk(
    client, review_user_token, review_user, event, review, other_review
):
    with scope(event=event):
        event.active_review_phase.can_see_other_reviews = "always"
        event.active_review_phase.save()
        other_review.submission.speakers.add(review_user)
    response = client.get(
        event.api_urls.reviews,
        follow=True,
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert len(content["results"]) == 1, content


@pytest.mark.django_db
def test_reviewer_can_create_review(
    client, review_user_token, event, submission, review_user
):
    with scope(event=event):
        assert event.active_review_phase.can_review is True
        assert not Review.objects.filter(
            submission=submission, user=review_user
        ).exists()
        url = event.api_urls.reviews
        data = {"submission": submission.code, "text": "This is a new review."}

    response = client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 201, response.text

    with scope(event=event):
        new_review = Review.objects.get(submission=submission, user=review_user)
        assert new_review.text == data["text"]
        assert new_review.score is None


@pytest.mark.django_db
def test_reviewer_can_create_review_with_scores(
    client,
    review_user_token,
    event,
    submission,
    review_user,
    review_score_category,
    review_score_value_positive,
):
    with scope(event=event):
        assert event.active_review_phase.can_review is True
        url = event.api_urls.reviews
        data = {
            "submission": submission.code,
            "text": "This is a new review with scores.",
            "scores": [review_score_value_positive.pk],
        }

    response = client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 201, response.text

    with scope(event=event):
        new_review = Review.objects.get(submission=submission, user=review_user)
        assert new_review.text == data["text"]
        assert new_review.scores.count() == 1
        assert new_review.scores.first() == review_score_value_positive
        assert (
            new_review.score
            == review_score_value_positive.value * review_score_category.weight
        )


@pytest.mark.django_db
def test_reviewer_cannot_create_duplicate_review(
    client, review_user_token, event, review
):
    with scope(event=event):
        url = event.api_urls.reviews
        data = {"submission": review.submission.code, "text": "Duplicate review."}

    response = client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 400, response.text
    content = json.loads(response.text)
    assert "You have already reviewed this submission." in content["submission"]


@pytest.mark.django_db
def test_reviewer_cannot_create_review_for_own_submission(
    client, review_user_token, event, submission, review_user
):
    with scope(event=event):
        submission.speakers.add(review_user)
        submission.save()
        url = event.api_urls.reviews
        data = {"submission": submission.code, "text": "Review for my own talk."}

    response = client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 400, response.text
    content = json.loads(response.text)
    assert content["submission"]


@pytest.mark.django_db
def test_reviewer_cannot_create_review_if_phase_disallows(
    client, review_user_token, event, submission
):
    with scope(event=event):
        phase = event.active_review_phase
        phase.can_review = False
        phase.save()
        url = event.api_urls.reviews
        data = {"submission": submission.code, "text": "Review when phase closed."}

    response = client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 403, response.text


@pytest.mark.django_db
def test_anonymous_cannot_create_review(client, event, submission):
    url = event.api_urls.reviews
    data = {"submission": submission.code, "text": "Anonymous review."}
    response = client.post(url, data=json.dumps(data), content_type="application/json")
    assert response.status_code == 401, response.text


@pytest.mark.django_db
def test_reviewer_can_update_own_review_text(client, review_user_token, event, review):
    with scope(event=event):
        assert event.active_review_phase.can_review is True
        url = event.api_urls.reviews + f"{review.pk}/"
        new_text = "This is an updated review text."
        data = {"text": new_text}

    response = client.patch(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 200, response.text

    with scope(event=event):
        review.refresh_from_db()
        assert review.text == new_text


@pytest.mark.django_db
def test_reviewer_can_update_own_review_scores(
    client,
    review_user_token,
    event,
    review,
    review_score_category,
    review_score_value_positive,
    review_score_value_negative,
):
    with scope(event=event):
        assert event.active_review_phase.can_review is True
        review.scores.add(review_score_value_negative)
        review.save()
        initial_score = review.score

        url = event.api_urls.reviews + f"{review.pk}/"
        data = {"scores": [review_score_value_positive.pk]}

    response = client.patch(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 200, response.text

    with scope(event=event):
        review.refresh_from_db()
        assert review.scores.count() == 1
        assert review.scores.first() == review_score_value_positive
        assert review.score != initial_score
        assert (
            review.score
            == review_score_value_positive.value * review_score_category.weight
        )


@pytest.mark.django_db
def test_reviewer_cannot_add_multiple_scores_same_category(
    client,
    review_user_token,
    event,
    review,
    review_score_category,
    review_score_value_positive,
    review_score_value_negative,
):
    with scope(event=event):
        assert event.active_review_phase.can_review is True
        review.scores.add(review_score_value_negative)
        review.save()
        initial_score = review.score

        url = event.api_urls.reviews + f"{review.pk}/"
        data = {
            "scores": [review_score_value_positive.pk, review_score_value_negative.pk]
        }

    response = client.patch(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 400, response.text

    with scope(event=event):
        review.refresh_from_db()
        assert review.scores.count() == 1
        assert review.scores.first() == review_score_value_negative
        assert review.score == initial_score


@pytest.mark.django_db
def test_reviewer_cannot_update_other_review(
    client, review_user_token, event, other_review
):
    with scope(event=event):
        url = event.api_urls.reviews + f"{other_review.pk}/"
        data = {"text": "Trying to update someone else's review."}

    response = client.patch(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 403, response.text


@pytest.mark.django_db
def test_reviewer_cannot_update_review_if_phase_disallows(
    client, review_user_token, event, review
):
    with scope(event=event):
        phase = event.active_review_phase
        phase.can_review = False
        phase.save()
        url = event.api_urls.reviews + f"{review.pk}/"
        data = {"text": "Update when phase closed."}

    response = client.patch(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 403, response.text


@pytest.mark.django_db
def test_anonymous_cannot_update_review(client, event, review):
    url = event.api_urls.reviews + f"{review.pk}/"
    data = {"text": "Anonymous update."}
    response = client.patch(url, data=json.dumps(data), content_type="application/json")
    assert response.status_code == 404, response.text


@pytest.mark.django_db
def test_reviewer_can_delete_own_review(client, review_user_token, event, review):
    with scope(event=event):
        assert event.active_review_phase.can_review is True
        review_pk = review.pk
        assert Review.objects.filter(pk=review_pk).exists()
        url = event.api_urls.reviews + f"{review_pk}/"

    response = client.delete(
        url, headers={"Authorization": f"Token {review_user_token.token}"}
    )
    assert response.status_code == 204, response.text

    with scope(event=event):
        assert not Review.objects.filter(pk=review_pk).exists()


@pytest.mark.django_db
def test_reviewer_cannot_delete_other_review(
    client, review_user_token, event, other_review
):
    with scope(event=event):
        assert Review.objects.filter(pk=other_review.pk).exists()
        url = event.api_urls.reviews + f"{other_review.pk}/"

    response = client.delete(
        url, headers={"Authorization": f"Token {review_user_token.token}"}
    )
    assert response.status_code == 403, response.text

    with scope(event=event):
        assert Review.objects.filter(pk=other_review.pk).exists()


@pytest.mark.django_db
def test_reviewer_cannot_delete_review_if_phase_disallows(
    client, review_user_token, event, review
):
    with scope(event=event):
        phase = event.active_review_phase
        phase.can_review = False
        phase.save()
        assert Review.objects.filter(pk=review.pk).exists()
        url = event.api_urls.reviews + f"{review.pk}/"

    response = client.delete(
        url, headers={"Authorization": f"Token {review_user_token.token}"}
    )
    assert response.status_code == 403, response.text

    with scope(event=event):
        assert Review.objects.filter(pk=review.pk).exists()


@pytest.mark.django_db
def test_anonymous_cannot_delete_review(client, event, review):
    url = event.api_urls.reviews + f"{review.pk}/"
    response = client.delete(url)
    assert response.status_code == 404, response.text
