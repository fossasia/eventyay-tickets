import pytest

from stayseated.core.services.user import get_user, update_user


@pytest.mark.asyncio
async def test_get_user_requires_parameters():
    with pytest.raises(Exception):
        await get_user(None, None)


@pytest.mark.asyncio
async def test_update_user_requires_id():
    with pytest.raises(Exception):
        await update_user({}, {"data": True})
