import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_frab_import_minimal(superuser):
    call_command('init')
