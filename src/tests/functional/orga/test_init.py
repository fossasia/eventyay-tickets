import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_init_minimal(superuser):
    call_command('init')
