import pytest
from django_scopes import scope

from pretalx.orga.templatetags.orga_edit_link import orga_edit_link
from pretalx.orga.templatetags.review_score import _review_score_number, review_score


@pytest.mark.parametrize(
    "score,expected",
    (
        (3, "3"),
        (0, "0"),
        (3.0, "3"),
        (1.5, "1.5"),
        (None, "×"),
    ),
)
@pytest.mark.django_db()
def test_templatetag_review_score(score, expected, event):
    with scope(event=event):
        assert _review_score_number(event, score) == expected


@pytest.mark.django_db
def test_template_tag_review_score_numeric(review):
    with scope(event=review.submission.event):
        review.submission.current_score = 1
        review.save()
        assert review_score(None, review.submission) == "1"


@pytest.mark.parametrize(
    "url,target,result",
    (
        (
            "https://foo.bar",
            None,
            '<a href="https://foo.bar" class="btn btn-xs btn-outline-primary orga-edit-link ml-auto" title="Edit"><i class="fa fa-pencil"></i></a>',
        ),
        (
            "https://foo.bar",
            "",
            '<a href="https://foo.bar" class="btn btn-xs btn-outline-primary orga-edit-link ml-auto" title="Edit"><i class="fa fa-pencil"></i></a>',
        ),
        (
            "https://foo.bar",
            "target",
            '<a href="https://foo.bar#target" class="btn btn-xs btn-outline-primary orga-edit-link ml-auto" title="Edit"><i class="fa fa-pencil"></i></a>',
        ),
    ),
)
def test_templatetag_orga_edit_link(url, target, result):
    assert orga_edit_link(url, target) == result
