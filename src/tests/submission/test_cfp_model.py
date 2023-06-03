import datetime as dt

import pytest
from django_scopes import scope

from pretalx.submission.models import SubmissionType


@pytest.mark.django_db
@pytest.mark.parametrize(
    "deadline,deadlines,is_open",
    (
        (dt.datetime(year=2000, month=10, day=20), [], False),  # CfP deadline past
        (
            dt.datetime(year=2000, month=10, day=20),
            [dt.datetime(year=2000, month=11, day=20)],
            False,
        ),  # CfP deadline past with past other deadlines
        (
            dt.datetime(year=2000, month=10, day=20),
            [
                dt.datetime(year=2000, month=11, day=20),
                dt.datetime(2200, month=10, day=20),
            ],
            True,
        ),  # CfP deadline past with past and future other deadlines
        (dt.datetime(year=2200, month=10, day=20), [], True),  # CfP deadline future
        (
            dt.datetime(year=2200, month=10, day=20),
            [dt.datetime(year=2000, month=11, day=20)],
            True,
        ),  # CfP deadline future with past other deadlines
        (
            dt.datetime(year=2200, month=10, day=20),
            [
                dt.datetime(year=2000, month=11, day=20),
                dt.datetime(2200, month=10, day=20),
            ],
            True,
        ),  # CfP deadline future with past and future other deadlines
        (None, [], True),  # no CfP deadline
        (
            None,
            [dt.datetime(year=2000, month=11, day=20)],
            True,
        ),  # no CfP deadline with past other deadlines
        (
            None,
            [
                dt.datetime(year=2000, month=11, day=20),
                dt.datetime(2200, month=10, day=20),
            ],
            True,
        ),  # no CfP deadline with past and future other deadlines
    ),
)
def test_cfp_model_is_open(event, deadline, deadlines, is_open):
    with scope(event=event):
        event.cfp.deadline = deadline.replace(tzinfo=event.tz) if deadline else deadline
        event.cfp.save()
        assert event.slug in str(event.cfp)

        assert event.submission_types.count() == 1

        for dline in deadlines:
            SubmissionType.objects.create(
                event=event, name=str(dline), deadline=dline.astimezone(event.tz)
            )

        assert event.cfp.is_open == is_open
