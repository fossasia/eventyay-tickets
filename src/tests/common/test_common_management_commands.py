import pytest
import responses
from django.core.management import call_command

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
    call_command("regenerate_css", event=event.slug)


@pytest.mark.django_db
def test_common_test_regenerate_css_wrong_slug(event):
    call_command("regenerate_css", event=event.slug + "wrong")


@pytest.mark.django_db
def test_common_uncallable(event):
    with pytest.raises(OSError):
        call_command("init")
    with pytest.raises(Exception):
        call_command("shell_scoped")
