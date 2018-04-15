import pytest

from pretalx.event.models import Organiser
from pretalx.event.utils import create_organiser_with_user


@pytest.mark.django_db
def test_user_organiser_init(user):
    assert Organiser.objects.count() == 0
    assert user.teams.count() == 0
    create_organiser_with_user(name='Name', slug='slug', user=user)
    assert Organiser.objects.count() == 1
    assert user.teams.count() == 1
    assert user.teams.get().organiser == Organiser.objects.get()
