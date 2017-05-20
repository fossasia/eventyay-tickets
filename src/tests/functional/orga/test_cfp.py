import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_delete_submission_type(orga_client, submission_type, default_submission_type):
    assert default_submission_type.event.submission_types.count() == 2
    response = orga_client.get(reverse(f'orga:cfp.type.delete', kwargs={'pk': submission_type.pk, 'event': submission_type.event.slug}), follow=True)
    assert response.status_code == 200
    assert default_submission_type.event.submission_types.count() == 1


@pytest.mark.django_db
def test_delete_last_submission_type(orga_client, event):
    submission_type = event.cfp.default_type
    assert submission_type.event.submission_types.count() == 1
    response = orga_client.get(reverse(f'orga:cfp.type.delete', kwargs={'pk': submission_type.pk, 'event': submission_type.event.slug}), follow=True)
    assert response.status_code == 200
    assert submission_type.event.submission_types.count() == 1


@pytest.mark.django_db
def test_delete_default_submission_type(orga_client, submission_type, default_submission_type):
    assert default_submission_type.event.submission_types.count() == 2
    response = orga_client.get(reverse(f'orga:cfp.type.delete', kwargs={'pk': default_submission_type.pk, 'event': default_submission_type.event.slug}), follow=True)
    assert response.status_code == 200
    assert default_submission_type.event.submission_types.count() == 2
