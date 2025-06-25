import logging

import requests
from django.core.files.base import ContentFile

from venueless.core.models import User
from venueless.storage.models import StoredFile


def update_user_profile_from_social(
    user: User, network, *, name, url, avatar_url=None, avatar_media_type=None
):
    if name and not user.profile.get("display_name"):
        user.profile["display_name"] = name

    if avatar_url and not user.profile.get("avatar", {}).get("url"):
        content_types = {
            "png": "image/png",
            "jpeg": "image/jpeg",
            "jpg": "image/jpeg",
            "gif": "image/gif",
        }
        ext = avatar_url.rsplit(".", 1)[-1]
        if "/" in ext:
            ext = ".png"  # just a default guess
        try:
            r = requests.get(avatar_url)
            r.raise_for_status()
            c = ContentFile(r.content)
            sf = StoredFile.objects.create(
                world=user.world,
                user=user,
                filename=f"avatar.{ext}",
                type=avatar_media_type or content_types.get(ext.lower(), "image/png"),
                public=True,
            )
            sf.file.save(f"avatar.{ext}", c)
        except:
            logging.exception("Could not download avatar")
        else:
            user.profile["avatar"] = {
                "url": sf.file.url,
            }

    if url:
        user.profile.setdefault("fields", {})

        for field in user.world.config.get("profile_fields", []):
            if field.get("type") == "link" and field.get("network") == network:
                user.profile["fields"][field["id"]] = url

    user.save(update_fields=["profile"])
