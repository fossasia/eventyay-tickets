import pytest
from django.core.exceptions import ValidationError

from pretalx.common.forms.validators import ZXCVBNValidator


@pytest.mark.parametrize('score,works', (
    (-1, False),
    (0, True),
    (2, True),
    (4, True),
    (5, False),
))
def test_zxcvbn_validator_init_works(score, works):
    if works:
        ZXCVBNValidator(min_score=score)
    else:
        with pytest.raises(Exception):
            ZXCVBNValidator(min_score=score)


@pytest.mark.parametrize('password,works', (
    ('password', False),
    ('theMightyPassword', True),
))
def test_password_validation(password, works):
    if works:
        ZXCVBNValidator()(password)
    else:
        with pytest.raises(ValidationError):
            ZXCVBNValidator()(password)
