import pytest
from django_scopes import scope

from pretalx.common.tasks import regenerate_css


@pytest.mark.django_db
def test_regenerate_css_with_new_checksum(event):
    with scope(event=event):
        event.primary_color = "#ff0000"
        event.save()

        regenerate_css(event.pk)
        regenerate_css(event.pk)  # Second time will match the checksum
