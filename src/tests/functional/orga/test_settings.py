import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_create_room(orga_client, event):
    assert event.rooms.count() == 0
    response = orga_client.post(
        reverse('orga:settings.rooms.create', kwargs={'event': event.slug}),
        follow=True,
        data={'name_0': 'A room'}
    )
    assert response.status_code == 200
    assert event.rooms.count() == 1
    assert str(event.rooms.first().name) == 'A room'


@pytest.mark.django_db
def test_edit_room(orga_client, event, room):
    assert event.rooms.count() == 1
    assert str(event.rooms.first().name) != 'A room'
    response = orga_client.post(
        reverse('orga:settings.rooms.edit', kwargs={'event': event.slug, 'pk': room.pk}),
        follow=True,
        data={'name_0': 'A room'}
    )
    assert response.status_code == 200
    assert event.rooms.count() == 1
    assert str(event.rooms.first().name) == 'A room'


@pytest.mark.django_db
def test_delete_room(orga_client, event, room):
    assert event.rooms.count() == 1
    response = orga_client.get(
        reverse('orga:settings.rooms.delete', kwargs={'event': event.slug, 'pk': room.pk}),
        follow=True,
    )
    assert response.status_code == 200
    assert event.rooms.count() == 0
