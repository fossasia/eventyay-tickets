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
    if not settings.LINKEDIN_CLIENT_ID:
        return HttpResponse("LinkedIn is not configured", status=400)

    request.session["social_linkedin_session"] = data
    request.session["social_linkedin_state"] = get_random_string(16)

    payload = {
        "response_type": "code",
        "client_id": settings.LINKEDIN_CLIENT_ID,
        "redirect_uri": urljoin(settings.SITE_URL, reverse("social:linkedin.return")),
        "scope": "r_liteprofile",
        "state": request.session["social_linkedin_state"],
    }

    return redirect(
        f"https://www.linkedin.com/oauth/v2/authorization?{urlencode(payload)}"
    )


def return_view(request):
    if not request.session.get("social_linkedin_session"):
        return HttpResponse("Invalid session", status=403)

    try:
        r = requests.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            {
                "code": request.GET.get("code"),
                "grant_type": "authorization_code",
                "redirect_uri": urljoin(
                    settings.SITE_URL, reverse("social:linkedin.return")
                ),
                "client_id": settings.LINKEDIN_CLIENT_ID,
                "client_secret": settings.LINKEDIN_CLIENT_SECRET,
            },
        )
        r.raise_for_status()
        d = r.json()
    except requests.RequestException:
        logger.exception("OAuth failed")
        return redirect(
            request.session["social_linkedin_session"].get("return_url")
            + "#status=failed"
        )

    if "access_token" not in d:
        logger.error(f"OAuth failed: {d}")
        return redirect(
            request.session["social_linkedin_session"].get("return_url")
            + "#status=failed"
        )

    access_token = d["access_token"]

    try:
        r = requests.get(
            "https://api.linkedin.com/v2/me?projection=(id,localizedFirstName,localizedLastName,vanityName,"
            "profilePicture(displayImage~digitalmediaAsset:playableStreams))",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )
        r.raise_for_status()
        d = r.json()
    except requests.RequestException:
        logger.exception("OAuth userinfo failed")
        return redirect(
            request.session["social_linkedin_session"].get("return_url")
            + "#status=failed"
        )

    user = User.objects.get(
        pk=request.session["social_linkedin_session"].get("user"),
        world=request.session["social_linkedin_session"].get("world"),
    )

    user.social_login_id_linkedin = d["id"]
    user.save(update_fields=["social_login_id_linkedin"])

    kwargs = {}
    try:
        kwargs.update(
            {
                "avatar_url": d["profilePicture"]["displayImage~"]["elements"][0][
                    "identifiers"
                ][0]["identifier"],
                "avatar_media_type": d["profilePicture"]["displayImage~"]["elements"][
                    0
                ]["identifiers"][0]["mediaType"],
            }
        )
    except (KeyError, IndexError):
        logger.exception("Could not fetch LinkedIn avatar")

    update_user_profile_from_social(
        user,
        "linkedin",
        name=d["localizedFirstName"] + " " + d["localizedLastName"],
        url=("https://www.linkedin.com/in/" + d["vanityName"])
        if "vanityName" in d
        else None,
        **kwargs,
    )

    return redirect(
        request.session["social_linkedin_session"].get("return_url") + "#status=success"
    )
