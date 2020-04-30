import pytest

from venueless.core.services.user import get_user, update_user


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_get_user_requires_parameters():
    with pytest.raises(Exception):
        await get_user("sample")


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_update_user_requires_valid_id():
    with pytest.raises(Exception):
        await update_user("sample", "foo", public_data={"data": True})


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_get_user_by_id_without_error():
    assert await get_user("sample", with_id=1) is None
