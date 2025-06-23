import datetime as dt

import pytest
from django.utils.timezone import now
from django_scopes import scope

from pretalx.event.stages import STAGE_ORDER, in_stage


@pytest.mark.django_db
@pytest.mark.parametrize(
    "target,is_public,from_delta,to_delta,deadline_delta,has_submissions",
    (
        ("PREPARATION", False, 2, 3, 1, False),
        ("PREPARATION", False, 2, 3, 1, True),
        ("CFP_OPEN", True, 2, 3, 1, False),
        ("CFP_OPEN", True, 2, 3, 1, True),
        ("REVIEW", True, 2, 3, -1, True),
        ("SCHEDULE", True, 2, 3, -1, False),
        ("EVENT", True, -2, 3, -1, False),
        ("EVENT", True, -2, 3, -1, True),
        ("EVENT", True, 0, 0, -1, False),
        ("EVENT", True, 0, 0, -1, True),
        ("WRAPUP", True, -2, -1, -1, True),
        ("WRAPUP", True, -2, -1, -1, False),
    ),
)
def test_event_stages(
    event,
    submission,
    target,
    is_public,
    from_delta,
    to_delta,
    deadline_delta,
    has_submissions,
):
    with scope(event=event):
        _now = now()
        event.is_public = is_public
        event.date_from = (_now + dt.timedelta(days=from_delta)).date()
        event.date_to = (_now + dt.timedelta(days=to_delta)).date()
        event.cfp.deadline = _now + dt.timedelta(days=deadline_delta)
        event.save()
        event.cfp.save()
        event = event.__class__.objects.get(pk=event.pk)
        if not has_submissions:
            submission.state = "DELETED"
            submission.save()
        for stage in STAGE_ORDER:
            assert in_stage(event, stage) == (
                stage == target
            ), f'Event is{" not" if stage == target else ""} {stage} when it should be {target}!'
            if stage == target and target != "WRAPUP":
                break
