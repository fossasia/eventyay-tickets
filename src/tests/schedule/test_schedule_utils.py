import pytest
from django_scopes import scope

from pretalx.schedule.utils import guess_schedule_version


@pytest.mark.django_db
@pytest.mark.parametrize('previous,suggestion', (
    (None, '0.1'),
    ('0.1', '0.2'),
    ('0,2', '0,3'),
    ('0-3', '0-4'),
    ('0_4', '0_5'),
    ('1.0.1', '1.0.2'),
    ('Nichtnumerisch', ''),
    ('1.someting', ''),
    ('something.1', 'something.2'),
))
def test_schedule_version_guessing(event, previous, suggestion):
    with scope(event=event):
        if previous:
            event.release_schedule(previous)
        assert guess_schedule_version(event) == suggestion
