import pytest

from pretalx.orga.templatetags.review_score import (
    _review_score_number, _review_score_override,
)


@pytest.fixture
def event_with_score_context(event):
    event.settings.set('review_score_name_0', 'meh.')
    event.settings.set('review_score_name_1', 'okay')
    event.settings.set('review_score_name_2', 'good')
    event.settings.set('review_score_name_3', 'great')
    event.settings.set('review_min_score', 0)
    event.settings.set('review_max_score', 3)

    class request:
        pass

    r = request()
    r.event = event
    return {'request': r}


@pytest.mark.parametrize('score,expected', (
    (3, '3/3 (»great«)'),
    (2, '2/3 (»good«)'),
    (1, '1/3 (»okay«)'),
    (0, '0/3 (»meh.«)'),
    (1.5, '1.5/3'),
    (None, 'ø'),
))
@pytest.mark.django_db()
def test_templatetag_review_score(score, expected, event_with_score_context):
    assert _review_score_number(event_with_score_context, score) == expected


@pytest.mark.parametrize('positive,negative,expected', (
    (1, 0, '<i class="fa fa-arrow-circle-up override text-success"></i>'),
    (0, 1, '<i class="fa fa-arrow-circle-down override text-danger"></i>'),
    (2, 0, '<i class="fa fa-arrow-circle-up override text-success"></i> 2'),
    (0, 2, '<i class="fa fa-arrow-circle-down override text-danger"></i> 2'),
    (1, 1, '<i class="fa fa-arrow-circle-up override text-success"></i> 1<i class="fa fa-arrow-circle-down override text-danger"></i> 1'),
))
@pytest.mark.django_db()
def test_templatetag_review_score_overrid(positive, negative, expected):
    assert _review_score_override(positive, negative) == expected
