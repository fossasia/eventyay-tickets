import pytest


@pytest.mark.django_db
def test_orga_can_show_cards(orga_client, event, slot):
    response = orga_client.get(event.orga_urls.submission_cards)
    assert response.status_code == 200
