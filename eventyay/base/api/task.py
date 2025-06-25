import datetime as dt
import logging
import uuid
from http import HTTPStatus

import jwt
import requests
from celery import shared_task
from django.conf import settings

from venueless.core.models.auth import ShortToken
from eventyay.base.models.world import World

logger = logging.getLogger(__name__)


def generate_video_token(world, days, number, traits, long=False):
    """
    Generate video token
    :param world: World object
    :param days: A integer representing the number of days the token is valid
    :param number: A integer representing the number of tokens to generate
    :param traits: A dictionary representing the traits of the token
    :param long: A boolean representing if the token is long or short
    :return: A list of tokens
    """
    jwt_secrets = world.config.get("JWT_secrets", [])
    if not jwt_secrets:
        logger.error("JWT_secrets is missing or empty in the configuration")
        return
    jwt_config = jwt_secrets[0]
    secret = jwt_config.get("secret")
    audience = jwt_config.get("audience")
    issuer = jwt_config.get("issuer")
    iat = dt.datetime.now(dt.timezone.utc)
    exp = iat + dt.timedelta(days=days)
    result = []
    bulk_create = []
    for _ in range(number):
        payload = {
            "iss": issuer,
            "aud": audience,
            "exp": exp,
            "iat": iat,
            "uid": str(uuid.uuid4()),
            "traits": traits,
        }
        token = jwt.encode(payload, secret, algorithm="HS256")
        if long:
            result.append(token)
        else:
            st = ShortToken(world=world, long_token=token, expires=exp)
            result.append(st.short_token)
            bulk_create.append(st)

    if not long:
        ShortToken.objects.bulk_create(bulk_create)
    return result


def generate_talk_token(video_settings, video_tokens, event_slug):
    """
    Generate talk token
    :param video_settings: A dictionary representing the video settings
    :param video_tokens: A list of video tokens
    :param event_slug:  A string representing the event slug
    :return: A token
    """
    iat = dt.datetime.now(dt.timezone.utc)
    exp = iat + dt.timedelta(days=30)
    payload = {
        "exp": exp,
        "iat": iat,
        "video_tokens": video_tokens,
        "slug": event_slug,
    }
    token = jwt.encode(payload, video_settings.get("secret"), algorithm="HS256")
    return token


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def configure_video_settings_for_talks(
    self, world_id, days, number, traits, long=False
):
    """
    Configure video settings for talks
    :param self: instance of the task
    :param world_id: A integer representing the world id
    :param days: A integer representing the number of days the token is valid
    :param number: A integer representing the number of tokens to generate
    :param traits: A dictionary representing the traits of the token
    :param long: A boolean representing if the token is long or short
    """
    try:
        if not isinstance(world_id, str) or not world_id.isalnum():
            raise ValueError("Invalid world_id format")
        world = World.objects.get(id=world_id)
        event_slug = world_id
        jwt_secrets = world.config.get("JWT_secrets", [])
        if not jwt_secrets:
            logger.error("JWT_secrets is missing or empty in the configuration")
            return
        jwt_config = jwt_secrets[0]
        video_tokens = generate_video_token(world, days, number, traits, long)
        talk_token = generate_talk_token(jwt_config, video_tokens, event_slug)
        header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {talk_token}",
        }
        payload = {
            "video_settings": {
                "audience": jwt_config.get("audience"),
                "issuer": jwt_config.get("issuer"),
                "secret": jwt_config.get("secret"),
            }
        }
        requests.post(
            "{}/api/configure-video-settings/".format(settings.EVENTYAY_TALK_BASE_PATH),
            json=payload,
            headers=header,
        )
        world.config["pretalx"] = {
            "event": event_slug,
            "domain": "{}".format(settings.EVENTYAY_TALK_BASE_PATH),
            "pushed": dt.datetime.now(dt.timezone.utc).isoformat(),
            "connected": True,
        }
        world.save()
    except requests.exceptions.ConnectionError as e:
        logger.error("Connection error: %s", e)
        self.retry(exc=e)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code in (
            HTTPStatus.UNAUTHORIZED.value,
            HTTPStatus.FORBIDDEN.value,
            HTTPStatus.NOT_FOUND.value,
        ):
            logger.error("Non-retryable error: %s", e)
            raise
        logger.error("HTTP error: %s", e)
        self.retry(exc=e)
    except ValueError as e:
        logger.error("Error configuring video settings: %s", e)
