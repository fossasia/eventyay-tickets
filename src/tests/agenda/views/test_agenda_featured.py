import pytest
from django_scopes import scope


@pytest.mark.django_db
@pytest.mark.parametrize("featured", ("always", "never", "pre_schedule"))
def test_featured_invisible_because_setting(
    client, django_assert_max_num_queries, event, featured, confirmed_submission
):
    with scope(event=event):
        event.settings.show_featured = featured
        confirmed_submission.is_featured = True
        confirmed_submission.save()
    url = str(event.urls.featured)
    with django_assert_max_num_queries(18):
        response = client.get(url, follow=True)
    if featured == "never":
        assert response.status_code == 404
    else:
        assert response.status_code == 200
        url = url.replace("featured", "sneak")
        response = client.get(url)
        assert response.status_code == 301
        assert response.url == event.urls.featured


@pytest.mark.parametrize("featured", ("always", "never", "pre_schedule"))
@pytest.mark.django_db
def test_featured_invisible_because_schedule(
    client, django_assert_max_num_queries, event, featured
):
    with scope(event=event):
        event.settings.show_featured = featured
        event.release_schedule("42")
    with django_assert_max_num_queries(27):
        response = client.get(event.urls.featured)

    if featured != "always":
        # there might be multiple redirects to correct trailing slashes, so the
        # one we're looking for is not always the last one.
        assert response.status_code == 302
        assert response.url == event.urls.schedule
    else:
        assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("featured", ("always", "pre_schedule"))
def test_featured_visible_despite_schedule(
    client, django_assert_max_num_queries, event, featured
):
    event.settings.show_featured = featured
    event.settings.show_schedule = False
    with scope(event=event):
        event.release_schedule("42")
    with django_assert_max_num_queries(17):
        response = client.get(event.urls.featured, follow=True)
    assert response.status_code == 200
    assert "featured" in response.content.decode()


@pytest.mark.django_db
def test_featured_talk_list(
    client,
    django_assert_max_num_queries,
    event,
    confirmed_submission,
    other_confirmed_submission,
):
    confirmed_submission.is_featured = True
    confirmed_submission.save()

    event.settings.show_featured = True

    with django_assert_max_num_queries(18):
        response = client.get(event.urls.featured, follow=True)
    assert response.status_code == 200
    content = response.content.decode()
    assert confirmed_submission.title in content
    assert other_confirmed_submission.title not in content
