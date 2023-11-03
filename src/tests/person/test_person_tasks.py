import pytest

from pretalx.person.models import User


def mock_get_404(*args, **kwargs):
    class MockResponse:
        def __init__(self):
            self.status_code = 404

    return MockResponse()


@pytest.mark.django_db
def test_gravatar_refetch_called(user, caplog, mocker, event):
    # do not use save(), as this would trigger the fetch already
    User.objects.filter(pk=user.pk).update(get_gravatar=True)

    # patch requests.get to return a 404
    mocker.patch("pretalx.person.tasks.get", mock_get_404)
    mocker.patch("requests.get", mock_get_404)
    from pretalx.person import tasks

    tasks.refetch_gravatars(sender=event)

    user.refresh_from_db()
    assert user.get_gravatar is False
    assert (
        f"gravatar returned http 404 when getting avatar for user {user.name}"
        in caplog.text
    )


@pytest.mark.django_db
def test_gravatar_refetch_called_on_save(user, caplog, mocker):
    # patch requests.get to return a 404
    mocker.patch("pretalx.person.tasks.get", mock_get_404)
    mocker.patch("requests.get", mock_get_404)

    user.get_gravatar = True
    user.save()
    user.refresh_from_db()
    assert user.get_gravatar is False

    assert (
        f"gravatar returned http 404 when getting avatar for user {user.name}"
        in caplog.text
    )


@pytest.mark.django_db
def test_gravatar_refetch_on_incorrect_user(user, mocker, caplog):
    from pretalx.person import tasks

    tasks.gravatar_cache(user.pk)
    user.refresh_from_db()
    assert user.get_gravatar is False
    assert f"gravatar_cache() was called for user {user.id}, but user was not found or user has gravatar disabled"


@pytest.mark.django_db
def test_gravatar_refetch_on_missing_user(mocker, caplog):
    from pretalx.person import tasks

    tasks.gravatar_cache(1001)
    assert "gravatar_cache() was called for user 1001, but user was not found or user has gravatar disabled"
