import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import override_settings

from pretalx.common.css import validate_css
from pretalx.event.models import Event


@pytest.fixture
def valid_css():
    return '''
body {
  background-color: #000;
  display: none;
}
.some-descriptor {
  /* Dotted borders are IN! */
  border-style: dotted dashed solid double;
  BORDER-color: red green blue yellow;
}
#best-descriptor {
  border: 5px solid red;
}
@media print {
  #best-descriptor {
    border: 5px solid blue;
  }
}
'''


@pytest.fixture
def invalid_css(valid_css):
    return (
        valid_css
        + '''
a.other-descriptor {
    content: url("https://malicious.site.com");
}
'''
    )


def test_valid_css(valid_css):
    assert validate_css(valid_css) == valid_css


def test_invalid_css(invalid_css):
    with pytest.raises(ValidationError):
        validate_css(invalid_css)


@pytest.mark.django_db
@override_settings(COMPRESS_PRECOMPILERS=settings.COMPRESS_PRECOMPILERS_ORIGINAL)
def test_regenerate_css(event):
    from pretalx.common.tasks import regenerate_css

    event.primary_color = '#00ff00'
    event.settings.widget_css_checksum = 'placeholder'
    event.save()
    regenerate_css(event.pk)
    event = Event.objects.get(pk=event.pk)
    for local_app in ['agenda', 'cfp']:
        assert event.settings.get(f'{local_app}_css_file')
        assert event.settings.get(f'{local_app}_css_checksum')
    assert event.settings.widget_css_checksum != 'placeholder'
    assert event.settings.widget_css


@pytest.mark.django_db
def test_regenerate_css_no_color(event):
    from pretalx.common.tasks import regenerate_css

    event.primary_color = None
    event.save()
    regenerate_css(event.pk)
    event = Event.objects.get(pk=event.pk)
    for local_app in ['agenda', 'cfp']:
        assert not event.settings.get(f'{local_app}_css_file')
        assert not event.settings.get(f'{local_app}_css_checksum')
    assert not event.settings.widget_css


@pytest.mark.django_db
def test_regenerate_css_no_event():
    from pretalx.common.tasks import regenerate_css

    regenerate_css(123)
