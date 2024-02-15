import datetime as dt
import subprocess
from contextlib import suppress

import pytest
import responses
from django.core.management import call_command
from django_scopes import scope

from pretalx.event.models import Event


@pytest.mark.django_db
@responses.activate
def test_common_runperiodic():
    responses.add(
        responses.POST,
        "https://pretalx.com/.update_check/",
        json="{}",
        status=404,
        content_type="application/json",
    )
    call_command("runperiodic")


@pytest.mark.parametrize("stage", ("cfp", "review", "over", "schedule"))
@pytest.mark.django_db
def test_common_test_event(administrator, stage):
    call_command("create_test_event", stage=stage)
    assert Event.objects.get(slug="democon")


@pytest.mark.django_db
def test_common_test_event_with_seed(administrator):
    call_command("create_test_event", seed=1)
    assert Event.objects.get(slug="democon")


@pytest.mark.django_db
def test_common_test_event_without_user():
    call_command("create_test_event")
    assert Event.objects.count() == 0


@pytest.mark.django_db
def test_common_test_regenerate_css_global(event):
    call_command("regenerate_css")


@pytest.mark.django_db
def test_common_test_regenerate_css_single_event(event):
    event.settings.widget_checksum_en = "a"
    event.settings.agenda_css_checksum = "a"
    event.primary_color = "#ff0000"
    event.save()
    call_command("regenerate_css", "--silent", event=event.slug)


@pytest.mark.django_db
def test_common_test_regenerate_css_wrong_slug(event):
    call_command("regenerate_css", event=event.slug + "wrong")


@pytest.mark.django_db
def test_common_uncallable(event):
    with pytest.raises(OSError):
        call_command("init")
    with pytest.raises(Exception):  # noqa
        call_command("shell_scoped")


@pytest.mark.django_db
def test_common_custom_migrate_does_not_blow_up():
    call_command("migrate")


@pytest.mark.django_db
def test_common_custom_makemessages_does_not_blow_up():
    call_command("makemessages", "--keep-pot", locale=["de_DE"])
    with suppress(Exception):
        subprocess.run(
            [
                "git",
                "checkout",
                "--",
                "pretalx/locale/de_DE",
                "pretalx/locale/django.pot",
            ]
        )


@pytest.mark.django_db
def test_common_move_event(event, slot):
    with scope(event=event):
        old_start = event.date_from
        first_start = slot.start
    call_command(
        "move_event",
        event=event.slug,
        date=(event.date_from + dt.timedelta(days=1)).strftime("%Y-%m-%d"),
    )
    with scope(event=event):
        event.refresh_from_db()
        new_start = event.date_from
        assert new_start != old_start
        slot.refresh_from_db()
        assert slot.start != first_start
    call_command("move_event", event=event.slug)
    with scope(event=event):
        event.refresh_from_db()
        assert event.date_from == old_start
