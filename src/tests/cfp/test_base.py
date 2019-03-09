import pytest


@pytest.mark.django_db
def test_no_crash_on_incorrect_event(client, event):
    response = client.get(f'/{event.slug}typoe/',)
    assert response.status_code == 404


@pytest.mark.django_db
def test_no_crash_on_incorrect_event_for_orga(orga_client, event):
    response = orga_client.get(f'/{event.slug}typoe/',)
    assert response.status_code == 404


@pytest.mark.django_db
def test_no_crash_on_root_view(client, event, other_event):
    other_event.is_public = False
    other_event.save()
    response = client.get('/',)
    content = response.content.decode()
    assert response.status_code == 200
    assert event.slug in content
    assert other_event.slug not in content


@pytest.mark.django_db
def test_no_crash_on_root_view_as_organiser(orga_client, event, other_event):
    other_event.is_public = False
    other_event.save()
    response = orga_client.get('/',)
    content = response.content.decode()
    assert response.status_code == 200
    assert event.slug in content
    assert other_event.slug not in content


@pytest.mark.django_db
def test_no_crash_on_robots_txt(client):
    response = client.get('/robots.txt',)
    assert response.status_code == 200
