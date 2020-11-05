import pytest

from venueless.core.models import World
from venueless.core.services.user import create_user, get_user, update_user


@pytest.mark.django_db
def test_get_user_requires_parameters():
    with pytest.raises(Exception):
        get_user(World())


@pytest.mark.django_db
def test_update_user_requires_valid_id():
    with pytest.raises(Exception):
        update_user("sample", "foo", public_data={"data": True})


@pytest.mark.django_db
def test_update_user_empty(world):
    u = create_user(world_id="sample", client_id="1234")
    update_user("sample", str(u.pk), public_data={})


@pytest.mark.django_db
def test_get_user_by_id_without_error():
    assert get_user(World.objects.get(pk='sample'), with_id=1) is None
