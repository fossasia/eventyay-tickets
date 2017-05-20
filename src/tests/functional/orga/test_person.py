import json

import pytest
from django.urls import reverse


@pytest.mark.parametrize('search,results', (
    ('a', 0),
    ('aa', 0),
    ('aaa', 0),
    ('Jane S', 1),
    ('orgauser', 2),
))
@pytest.mark.django_db
def test_user_typeahead(orga_client, event, speaker, other_orga_user, search, results):
    response = orga_client.get(
        reverse('orga:event.user_list', kwargs={'event': event.slug}),
        data={'search': search}, follow=True,
    )
    assert response.status_code == 200
    content = json.loads(response.content.decode())
    assert content['count'] == results
    assert len(content['results']) == results

    if results:
        assert 'nick' in content['results'][0]
        assert 'name' in content['results'][0]
