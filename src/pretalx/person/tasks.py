import logging

from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
from django.dispatch import receiver
from requests import get

from pretalx.celery_app import app
from pretalx.common.signals import periodic_task
from pretalx.person.models.user import User

logger = logging.getLogger(__name__)


@app.task()
def gravatar_cache(person_id: int):
    user = User.objects.filter(pk=person_id, get_gravatar=True).first()

    if not user:
        logger.warning(
            f"gravatar_cache() was called for user {person_id}, but "
            "user was not found or user has gravatar disabled"
        )
        return

    r = get(
        f"https://www.gravatar.com/avatar/{user.gravatar_parameter}?s=512",
        timeout=10,
    )

    logger.info(
        f"gravatar returned http {r.status_code} when getting avatar for user {user.name}"
    )

    if 400 <= r.status_code <= 499:
        # avatar not found.
        user.get_gravatar = False
        user.save()
        return
    elif r.status_code != 200:
        return

    with NamedTemporaryFile(delete=True) as tmp_img:
        for chunk in r:
            tmp_img.write(chunk)
        tmp_img.flush()

        user.avatar.save(f"{user.gravatar_parameter}.jpg", File(tmp_img))
        user.get_gravatar = False
        user.save()

        logger.info(f"set avatar for user {user.name} to {user.avatar.url}")


@receiver(periodic_task)
def refetch_gravatars(sender, **kwargs):
    users_with_gravatar = User.objects.filter(get_gravatar=True)

    for user in users_with_gravatar:
        gravatar_cache.apply_async(args=(user.pk,))
