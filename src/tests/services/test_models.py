from io import StringIO

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_no_outstanding_migrations():
    out = StringIO()
    try:
        result = call_command("makemigrations", "--check", stdout=out, stderr=StringIO())
    except SystemExit as e:
        raise AssertionError(f"Pending migrations:\n{out.getvalue()}") from None
