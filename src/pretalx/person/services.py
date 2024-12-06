import datetime as dt

from django.utils.crypto import get_random_string
from django.utils.timezone import now


def create_user(email, name=None, pw_reset_days=60, event=None):
    from pretalx.person.models import SpeakerProfile, User

    user = User.objects.create_user(
        password=get_random_string(32),
        email=email.lower().strip(),
        name=(name or "").strip(),
        pw_reset_token=get_random_string(32),
        pw_reset_time=now() + dt.timedelta(days=pw_reset_days),
    )
    if event:
        SpeakerProfile.objects.get_or_create(user=user, event=event)
    return user
