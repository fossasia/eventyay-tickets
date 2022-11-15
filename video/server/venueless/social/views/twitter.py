import logging
from urllib.parse import urlencode, urljoin

import requests
from django.conf import settings
from django.core.signing import BadSignature, loads
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.crypto import get_random_string

from venueless.core.models.auth import User
from venueless.social.utils import update_user_profile_from_social

logger = logging.getLogger(__name__)


def start_view(request):
    try:
        data = loads(
            request.GET.get("token"), salt="venueless.social.start", max_age=600
        )
    except BadSignature:
        return HttpResponse("Invalid request token", status=403)
    if not settings.TWITTER_CLIENT_ID:
        return HttpResponse("Twitter is not configured", status=400)

    request.session["social_twitter_session"] = data
    request.session["social_twitter_state"] = get_random_string(16)
    request.session["social_twitter_challenge"] = get_random_string(16)

    payload = {
        "response_type": "code",
        "client_id": settings.TWITTER_CLIENT_ID,
        "redirect_uri": urljoin(settings.SITE_URL, reverse("social:twitter.return")),
        "scope": "users.read tweet.read",
        "state": request.session["social_twitter_state"],
        "code_challenge": request.session["social_twitter_challenge"],
        "code_challenge_method": "plain",
    }

    return redirect(f"https://twitter.com/i/oauth2/authorize?{urlencode(payload)}")


def return_view(request):
    if not request.session.get("social_twitter_session"):
        return HttpResponse("Invalid session", status=403)

    try:
        r = requests.post(
            "https://api.twitter.com/2/oauth2/token",
            {
                "code": request.GET.get("code"),
                "grant_type": "authorization_code",
                "redirect_uri": urljoin(
                    settings.SITE_URL, reverse("social:twitter.return")
                ),
                "code_verifier": request.session.get("social_twitter_challenge"),
            },
            auth=(settings.TWITTER_CLIENT_ID, settings.TWITTER_CLIENT_SECRET),
        )
        r.raise_for_status()
        d = r.json()
    except requests.RequestException:
        logger.exception("OAuth failed")
        return redirect(
            request.session["social_twitter_session"].get("return_url")
            + "#status=failed"
        )

    if "access_token" not in d:
        logger.error(f"OAuth failed: {d}")
        return redirect(
            request.session["social_twitter_session"].get("return_url")
            + "#status=failed"
        )

    access_token = d["access_token"]

    try:
        r = requests.get(
            "https://api.twitter.com/2/users/me?user.fields=id,name,username,profile_image_url,description",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )
        r.raise_for_status()
        d = r.json()
    except requests.RequestException:
        logger.exception("OAuth userinfo failed")
        return redirect(
            request.session["social_twitter_session"].get("return_url")
            + "#status=failed"
        )

    user = User.objects.get(
        pk=request.session["social_twitter_session"].get("user"),
        world=request.session["social_twitter_session"].get("world"),
    )

    user.social_login_id_twitter = d["data"]["id"]
    user.save(update_fields=["social_login_id_twitter"])

    update_user_profile_from_social(
        user,
        "twitter",
        name=d["data"]["name"],
        url="https://twitter.com/" + d["data"]["username"],
        avatar_url=d["data"].get("profile_image_url", "").replace("_normal.", "."),
    )

    return redirect(
        request.session["social_twitter_session"].get("return_url") + "#status=success"
    )
