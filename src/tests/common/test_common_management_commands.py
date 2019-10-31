import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_common_runperiodic():
    call_command('runperiodic')


@pytest.mark.django_db
def test_common_test_event():
    call_command('create_test_event')
