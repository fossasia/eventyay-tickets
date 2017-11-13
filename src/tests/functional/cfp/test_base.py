import pytest


@pytest.mark.django_db
def test_no_crash_on_incorrect_event(client, event):
    response = client.get(f'/{event.slug}typoe/',)
    assert response.status_code == 404


@pytest.mark.django_db
def test_no_crash_on_incorrect_event_for_orga(orga_client, event):
    response = orga_client.get(f'/{event.slug}typoe/',)
    assert response.status_code == 404
