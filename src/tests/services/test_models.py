import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_no_outstanding_migrations():
    result = call_command("makemigrations", "--dry-run", "--check", "--no-input", "-v", "0")
    assert result is None
