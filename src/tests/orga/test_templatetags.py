import pytest
from django_scopes import scope

from pretalx.orga.templatetags.orga_edit_link import orga_edit_link
from pretalx.orga.templatetags.review_score import (
    _review_score_number, _review_score_override, review_score,
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


@pytest.mark.parametrize(
    'score,expected',
    (
        (3, '3/3 (“great”)'),
        (2, '2/3 (“good”)'),
        (1, '1/3 (“okay”)'),
        (0, '0/3 (“meh.”)'),
        (1.5, '1.5/3'),
        (None, '×'),
    ),
)
@pytest.mark.django_db()
def test_templatetag_review_score(score, expected, event_with_score_context):
    with scope(event=event_with_score_context):
        assert _review_score_number(event_with_score_context, score) == expected


@pytest.mark.parametrize(
    'positive,negative,expected',
    (
        (1, 0, '<i class="fa fa-arrow-circle-up override text-success"></i>'),
        (0, 1, '<i class="fa fa-arrow-circle-down override text-danger"></i>'),
        (2, 0, '<i class="fa fa-arrow-circle-up override text-success"></i> 2'),
        (0, 2, '<i class="fa fa-arrow-circle-down override text-danger"></i> 2'),
        (
            1,
            1,
            '<i class="fa fa-arrow-circle-up override text-success"></i> 1<i class="fa fa-arrow-circle-down override text-danger"></i> 1',
        ),
    ),
)
@pytest.mark.django_db()
def test_templatetag_review_score_override(positive, negative, expected):
    assert _review_score_override(positive, negative) == expected


@pytest.mark.django_db
def test_template_tag_review_score(review):
    with scope(event=review.submission.event):
        review.override_vote = True
        review.submission.current_score = 0
        review.save()
        assert (
            '<i class="fa fa-arrow-circle-up override text-success"></i>'
            == review_score(None, review.submission)
        )


@pytest.mark.parametrize(
    'url,target,result',
    (
        (
            'https://foo.bar',
            None,
            '<a href="https://foo.bar" class="btn btn-xs btn-outline-primary orga-edit-link ml-auto" title="Edit"><i class="fa fa-pencil"></i></a>',
        ),
        (
            'https://foo.bar',
            '',
            '<a href="https://foo.bar" class="btn btn-xs btn-outline-primary orga-edit-link ml-auto" title="Edit"><i class="fa fa-pencil"></i></a>',
        ),
        (
            'https://foo.bar',
            'target',
            '<a href="https://foo.bar#target" class="btn btn-xs btn-outline-primary orga-edit-link ml-auto" title="Edit"><i class="fa fa-pencil"></i></a>',
        ),
    ),
)
def test_templatetag_orga_edit_link(url, target, result):
    assert orga_edit_link(url, target) == result
