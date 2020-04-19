import pytest

from pretalx.person.models.information import resource_path


@pytest.mark.django_db
def test_information_resource_path(information):
    assert resource_path(information, "foo").startswith(
        f"{information.event.slug}/speaker_information/foo"
    )
