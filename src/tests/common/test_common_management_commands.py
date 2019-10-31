import pytest
from django.core.management import call_command

from pretalx.event.models import Event


@pytest.mark.django_db
def test_common_runperiodic():
    call_command('runperiodic')


@pytest.mark.parametrize('stage', ('cfp', 'review', 'over', 'schedule'))
@pytest.mark.django_db
def test_common_test_event(administrator, stage):
    call_command('create_test_event', stage=stage)
    assert Event.objects.get(slug='democon')


@pytest.mark.django_db
def test_common_test_event_without_user():
    call_command('create_test_event')
    assert Event.objects.count() == 0
