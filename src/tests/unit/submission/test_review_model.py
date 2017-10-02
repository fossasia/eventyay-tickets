import pytest

from pretalx.submission.models import Review


@pytest.mark.django_db
@pytest.mark.parametrize('scores,expected', (
    ([], None),
    ([None], None),
    ([None, None], None),
    ([1], 1),
    ([1, None], 1),
    ([1, 2], 1.5),
    ([1, 2, None], 1.5),
))
def test_average_review_score(submission, scores, expected):
    speaker = submission.speakers.first()
    reviews = [Review(submission=submission, score=score, user=speaker) for score in scores]
    Review.objects.bulk_create(reviews)
    assert submission.average_score == expected
    submission.reviews.all().delete()
