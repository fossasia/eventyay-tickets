import logging

from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
from django.dispatch import receiver
from django.utils.timezone import now
from requests import get

from eventyay.celery_app import app
from eventyay.common.signals import minimum_interval, periodic_task
from eventyay.base.models import User
from eventyay.base.models.auth_token import UserApiToken

logger = logging.getLogger(__name__)


@app.task(name='eventyay.person.gravatar_cache')
def gravatar_cache(person_id: int):
    user = User.objects.filter(pk=person_id, get_gravatar=True).first()

    if not user:
        logger.warning(
            f'gravatar_cache() was called for user {person_id}, but user was not found or user has gravatar disabled'
        )
        return

    response = get(
        f'https://www.gravatar.com/avatar/{user.gravatar_parameter}?s=512',
        timeout=10,
    )

    logger.info(f'gravatar returned http {response.status_code} when getting avatar for user {user.name}')

    if 400 <= response.status_code <= 499:
        # avatar not found.
        user.get_gravatar = False
        user.save()
        return
    elif response.status_code != 200:
        return

    with NamedTemporaryFile(delete=True) as tmp_img:
        for chunk in response:
            tmp_img.write(chunk)
        tmp_img.flush()

        content_type = response.headers.get('Content-Type')
        if content_type == 'image/png':
            extension = 'png'
        elif content_type == 'image/gif':
            extension = 'gif'
        else:
            extension = 'jpg'

        user.get_gravatar = False
        user.save()
        user.avatar.save(f'{user.gravatar_parameter}.{extension}', File(tmp_img))

        logger.info(f'set avatar for user {user.name} to {user.avatar.url}')

    user.process_image('avatar', generate_thumbnail=True)


@receiver(periodic_task)
def refetch_gravatars(sender, **kwargs):
    users_with_gravatar = User.objects.filter(get_gravatar=True)

    for user in users_with_gravatar:
        gravatar_cache.apply_async(args=(user.pk,), ignore_result=True)


@receiver(signal=periodic_task)
@minimum_interval(minutes_after_success=60)
def run_update_check(sender, **kwargs):
    UserApiToken.objects.filter(expires__lt=now()).delete()
