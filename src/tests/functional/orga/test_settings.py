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


@pytest.mark.django_db
def test_delete_used_room(orga_client, event, room, slot):
    assert event.rooms.count() == 1
    assert slot.room == room
    response = orga_client.get(
        reverse('orga:settings.rooms.delete', kwargs={'event': event.slug, 'pk': room.pk}),
        follow=True,
    )
    assert response.status_code == 200
    assert event.rooms.count() == 1


@pytest.mark.django_db
def test_add_custom_css(event, orga_client):
    assert not event.custom_css
    with open('tests/functional/orga/fixtures/custom.css', 'r') as custom_css:
        response = orga_client.post(
            event.orga_urls.settings,
            {
                'name_0': event.name,
                'slug': event.slug,
                'is_public': event.is_public,
                'date_from': event.date_from,
                'date_to': event.date_to,
                'timezone': event.timezone,
                'email': event.email,
                'primary_color': event.primary_color,
                'custom_css': custom_css
            },
            follow=True
        )
    event.refresh_from_db()
    assert response.status_code == 200
    assert event.custom_css
