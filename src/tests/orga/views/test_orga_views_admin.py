import pytest


@pytest.mark.django_db
@pytest.mark.parametrize('is_administrator', (True, False))
def test_admin_dashboard_only_for_admin_user(orga_user, orga_client, is_administrator):
    orga_user.is_administrator = is_administrator
    orga_user.save()
    response = orga_client.get('/orga/admin/')
    assert (response.status_code == 200) is is_administrator
    assert ('Administrator information' in response.content.decode()) is is_administrator
