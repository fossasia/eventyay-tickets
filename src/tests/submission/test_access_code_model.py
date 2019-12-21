import math

import pytest

from pretalx.submission.models import SubmitterAccessCode


@pytest.mark.parametrize(
    "maximum_uses,redeemed,redemptions_left",
    (
        (0, 0, math.inf),
        (0, 10, math.inf),
        (None, 10, math.inf),
        (None, None, math.inf),
        (10, 1, 9),
        (10, 10, 0),
        (1, 1, 0),
        (1, 0, 1),
    ),
)
@pytest.mark.django_db
def test_access_code_redemptions_left(maximum_uses, redeemed, redemptions_left):
    assert (
        SubmitterAccessCode(
            maximum_uses=maximum_uses, redeemed=redeemed
        ).redemptions_left
        == redemptions_left
    )
