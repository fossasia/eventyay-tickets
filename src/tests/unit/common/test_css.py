import pytest
from django.core.exceptions import ValidationError

from pretalx.common.css import validate_css


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
