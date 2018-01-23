import pytest
from django.core.exceptions import ValidationError

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
  border-style: dotted dashed solid double;
  BORDER-color: red green blue yellow;
}
#best-descriptor {
  border: 5px solid red;
}
'''


@pytest.fixture
def invalid_css(valid_css):
    return valid_css + '''
a.other-descriptor {
    content: url("https://malicious.site.com");
}
'''


@pytest.fixture
def some_object():
    class Foo:
        pass
    return Foo()


def test_valid_css(valid_css):
    assert validate_css(valid_css) == valid_css


def test_invalid_css(invalid_css):
    with pytest.raises(ValidationError):
        validate_css(invalid_css)


@pytest.mark.django_db
def test_regenerate_css(event):
    from pretalx.common.tasks import regenerate_css
    event.primary_color = '#00ff00'
    event.save()
    regenerate_css(event.pk)
    event = Event.objects.get(pk=event.pk)
    for local_app in ['agenda', 'cfp', 'orga']:
        assert event.settings.get(f'{local_app}_css_file')
        assert event.settings.get(f'{local_app}_css_checksum')


@pytest.mark.django_db
def test_regenerate_css_no_color(event):
    from pretalx.common.tasks import regenerate_css
    event.primary_color = None
    event.save()
    regenerate_css(event.pk)
    event = Event.objects.get(pk=event.pk)
    for local_app in ['agenda', 'cfp', 'orga']:
        assert not event.settings.get(f'{local_app}_css_file')
        assert not event.settings.get(f'{local_app}_css_checksum')
