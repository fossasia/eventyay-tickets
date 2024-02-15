import pytest
from django_scopes import scope


@pytest.mark.parametrize(
    "url", ("widgets/schedule.js", "schedule/widgets/schedule.json")
)
@pytest.mark.parametrize(
    "show_schedule,show_widget_if_not_public,expected",
    (
        (True, False, 200),
        (True, True, 200),
        (False, False, 404),
        (False, True, 200),
    ),
)
@pytest.mark.django_db
def test_widget_pages(
    event,
    schedule,
    client,
    url,
    show_schedule,
    show_widget_if_not_public,
    expected,
    slot,
    other_slot,
):
    event.feature_flags["show_schedule"] = show_schedule
    event.feature_flags["show_widget_if_not_public"] = show_widget_if_not_public
    event.save()
    response = client.get(event.urls.base + url, follow=True)
    assert response.status_code == expected


@pytest.mark.django_db
def test_widget_data(
    client,
    event,
    schedule,
    slot,
    other_slot,
    django_assert_num_queries,
):
    event.feature_flags["show_schedule"] = True
    event.save()
    with django_assert_num_queries(11):
        response = client.get(
            event.urls.schedule + "widgets/schedule.json", follow=True
        )
    assert response.status_code == 200


@pytest.mark.django_db
def test_versioned_widget_data(client, event, schedule, slot):
    with scope(event=event):
        event.wip_schedule.freeze("new")

    response = client.get(
        event.urls.schedule + f"widgets/schedule.json?v={schedule.version}"
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_bogus_versioned_widget_data(client, event, schedule, slot):
    response = client.get(event.urls.schedule + "widgets/schedule.json?v=nopedinope")
    assert response.status_code == 200


@pytest.mark.django_db
def test_anon_cannot_access_wip_schedule(client, event, schedule, slot):
    response = client.get(event.urls.schedule + "widgets/schedule.json?v=wip")
    assert response.status_code == 404


@pytest.mark.django_db
def test_orga_can_access_wip_schedule(orga_client, event, schedule, slot):
    response = orga_client.get(event.urls.schedule + "widgets/schedule.json?v=wip")
    assert response.status_code == 200
