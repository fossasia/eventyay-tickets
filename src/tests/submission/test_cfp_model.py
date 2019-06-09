from datetime import datetime

import pytest
import pytz
from django_scopes import scope

from pretalx.submission.models import SubmissionType


@pytest.mark.django_db
@pytest.mark.parametrize('deadline,deadlines,is_open', (
    (datetime(year=2000, month=10, day=20), [], False),  # CfP deadline past
    (datetime(year=2000, month=10, day=20), [datetime(year=2000, month=11, day=20)], False),  # CfP deadline past with past other deadlines
    (datetime(year=2000, month=10, day=20), [datetime(year=2000, month=11, day=20), datetime(2200, month=10, day=20)], True),  # CfP deadline past with past and future other deadlines
    (datetime(year=2200, month=10, day=20), [], True),  # CfP deadline future
    (datetime(year=2200, month=10, day=20), [datetime(year=2000, month=11, day=20)], True),  # CfP deadline future with past other deadlines
    (datetime(year=2200, month=10, day=20), [datetime(year=2000, month=11, day=20), datetime(2200, month=10, day=20)], True),  # CfP deadline future with past and future other deadlines
    (None, [], True),  # no CfP deadline
    (None, [datetime(year=2000, month=11, day=20)], True),  # no CfP deadline with past other deadlines
    (None, [datetime(year=2000, month=11, day=20), datetime(2200, month=10, day=20)], True),  # no CfP deadline with past and future other deadlines
))
def test_cfp_model_is_open(event, deadline, deadlines, is_open):
    with scope(event=event):
        tz = pytz.timezone(event.timezone)
        event.cfp.deadline = tz.localize(deadline) if deadline else deadline
        event.cfp.save()
        assert event.slug in str(event.cfp)

        assert event.submission_types.count() == 1

        for dline in deadlines:
            SubmissionType.objects.create(event=event, name=str(dline), deadline=tz.localize(dline))

        assert event.cfp.is_open == is_open
