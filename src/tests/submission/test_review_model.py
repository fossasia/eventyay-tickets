import pytest
from django_scopes import scope

from pretalx.submission.models import Review


@pytest.mark.django_db
@pytest.mark.parametrize(
    "scores,expected",
    (
        ([], None),
        ([None], None),
        ([None, None], None),
        ([1], 1),
        ([1, None], 1),
        ([1, 2], 1.5),
        ([1, 2, None], 1.5),
        ([1, 1, 1, 5], 1),
    ),
)
def test_median_review_score(submission, scores, expected):
    with scope(event=submission.event):
        speaker = submission.speakers.first()
        reviews = [
            Review(submission=submission, score=score, user=speaker) for score in scores
        ]
        Review.objects.bulk_create(reviews)
        assert submission.median_score == expected
        submission.reviews.all().delete()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "score,expected",
    (
        (0, "0"),
        (1, "1"),
        (None, "×"),
    ),
)
def test_review_score_display(submission, score, expected, speaker):
    r = Review.objects.create(
        submission=submission,
        user=speaker,
        score=score,
    )
    assert submission.title in str(r)
    assert r.display_score == expected
