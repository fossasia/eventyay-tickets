import pytest
from django_scopes import scope

from pretalx.common.tasks import generate_widget_css, generate_widget_js, regenerate_css


@pytest.mark.django_db
def test_regenerate_css_with_new_checksum(event):
    with scope(event=event):
        event.primary_color = "#ff0000"
        event.save()

        regenerate_css(event.pk)
        regenerate_css(event.pk)  # Second time will match the checksum


@pytest.mark.django_db
def test_generate_widget_css(event):
    with scope(event=event):
        generate_widget_css(event, save=False)
        generate_widget_css(event, save=True)
        generate_widget_css(event, save=True)


@pytest.mark.django_db
def test_generate_widget_js(event):
    with scope(event=event):
        generate_widget_js(event, "en", save=False)
        generate_widget_js(event, "en", save=True)
        generate_widget_js(event, "en", save=True)
