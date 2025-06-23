import pytest

from venueless.core.models import BBBServer, World
from venueless.core.services.bbb import choose_server


@pytest.fixture
def empty_world(world):
    BBBServer.objects.all().delete()
    return World.objects.create(pk="W1", title="W1")


@pytest.mark.django_db
def test_always_choose_exclusive_server(empty_world):
    BBBServer.objects.create(
        active=True, url="https://a.example.com", secret="a", cost=0
    )
    BBBServer.objects.create(
        active=True,
        url="https://b.example.com",
        secret="b",
        cost=50,
        world_exclusive=empty_world,
    )
    assert choose_server(empty_world).secret == "b"
    assert choose_server(empty_world).secret == "b"


@pytest.mark.django_db
def test_do_not_use_exclusive_for_other_empty_world(empty_world):
    w2 = World.objects.create(pk="W2", title="W2")
    BBBServer.objects.create(
        active=True, url="https://a.example.com", secret="a", cost=50
    )
    BBBServer.objects.create(
        active=True,
        url="https://b.example.com",
        secret="b",
        cost=0,
        world_exclusive=w2,
    )
    assert choose_server(empty_world).secret == "a"
    assert choose_server(empty_world).secret == "a"
    assert choose_server(w2).secret == "b"
    assert choose_server(w2).secret == "b"


@pytest.mark.django_db
def test_prefer_server(empty_world):
    BBBServer.objects.create(
        active=True, url="https://a.example.com", secret="a", cost=50
    )
    BBBServer.objects.create(
        active=True,
        url="https://b.example.com",
        secret="b",
        cost=50,
    )
    assert (
        choose_server(empty_world, prefer_server="https://a.example.com").secret == "a"
    )
    assert (
        choose_server(empty_world, prefer_server="https://b.example.com").secret == "b"
    )
    assert (
        choose_server(empty_world, prefer_server="https://a.example.com").secret == "a"
    )
    assert (
        choose_server(empty_world, prefer_server="https://b.example.com").secret == "b"
    )


@pytest.mark.django_db
def test_never_choose_inactive(empty_world):
    BBBServer.objects.create(
        active=True, url="https://a.example.com", secret="a", cost=50
    )
    BBBServer.objects.create(
        active=False,
        url="https://b.example.com",
        secret="b",
        cost=10,
    )
    assert choose_server(empty_world).secret == "a"
    assert choose_server(empty_world).secret == "a"


@pytest.mark.django_db
def prefer_cost_round_robin(empty_world):
    BBBServer.objects.create(
        active=True, url="https://a.example.com", secret="a", cost=10
    )
    BBBServer.objects.create(
        active=False,
        url="https://b.example.com",
        secret="b",
        cost=15,
    )
    assert choose_server(empty_world).secret == "a"
    assert choose_server(empty_world).secret == "b"
    assert choose_server(empty_world).secret == "a"
    assert choose_server(empty_world).secret == "b"
    assert choose_server(empty_world).secret == "a"
    assert choose_server(empty_world).secret == "b"
