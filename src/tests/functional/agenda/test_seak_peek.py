import pytest


@pytest.mark.django_db
def test_sneak_peak_invisible_setting(client, event):
    event.settings.show_sneak_peek = False
    response = client.get(event.urls.sneakpeek, follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_sneak_peak_invisible_schedule(client, event):
    event.settings.show_sneak_peek = True
    event.release_schedule("42")
    response = client.get(event.urls.sneakpeek, follow=True)

    # there might be multiple redirects to correct trailing slashes, so the
    # one we're looking for is not always the last one.
    assert any(
        True for r in response.redirect_chain
        if r[0].rstrip('/') == event.urls.schedule.rstrip('/') and r[1] == 302
    )


@pytest.mark.django_db
def test_sneak_peak_visible(client, event):
    event.settings.show_sneak_peek = True
    response = client.get(event.urls.sneakpeek, follow=True)
    assert response.status_code == 200
    assert 'peek' in response.content.decode()


@pytest.mark.django_db
def test_sneak_peak_talk_list(client, event, confirmed_submission, other_confirmed_submission):
    confirmed_submission.is_featured = True
    confirmed_submission.save()

    event.settings.show_sneak_peek = True

    response = client.get(event.urls.sneakpeek, follow=True)
    assert response.status_code == 200
    content = response.content.decode()
    assert confirmed_submission.title in content
    assert other_confirmed_submission.title not in content
