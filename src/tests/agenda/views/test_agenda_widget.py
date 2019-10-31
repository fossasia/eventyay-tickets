import pytest


@pytest.mark.parametrize('url', (
    'v1.en.js',
    'v1.json',
    'v1.css',
))
@pytest.mark.parametrize('show_schedule,show_widget_if_not_public,expected', (
    (True, False, 200),
    (True, True, 200),
    (False, False, 404),
    (False, True, 200),
))
@pytest.mark.django_db
def test_widget_pages(event, schedule, client, url, show_schedule, show_widget_if_not_public, expected):
    event.settings.show_schedule = show_schedule
    event.settings.show_widget_if_not_public = show_widget_if_not_public
    response = client.get(event.urls.schedule + 'widget/' + url, follow=True)
    assert response.status_code == expected


@pytest.mark.parametrize('locale,expected', (
    ('lo', 404),
    ('en', 200),
))
@pytest.mark.django_db
def test_widget_wrong_locale(event, schedule, client, locale, expected):
    response = client.get(event.urls.schedule + 'widget/v1.' + locale + '.js')
    assert response.status_code == expected


@pytest.mark.django_db
def test_widget_with_primary_color(event, schedule, client):
    event.primary_color = '#abcdef'
    event.save()
    response = client.get(event.urls.schedule + 'widget/v1.css')
    assert event.primary_color in response.content.decode()
