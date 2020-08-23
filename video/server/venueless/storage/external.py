import mimetypes
import uuid

import requests
from bs4 import BeautifulSoup
from django.core.files.base import ContentFile
from django.utils.timezone import now

from venueless.storage.models import StoredFile


def get_extension_from_response(response):
    content_type = response.headers.get("Content-Type")
    if not content_type:
        return
    content_type = content_type.split(";")[0].strip()
    extension = mimetypes.guess_extension(content_type)
    ext_whitelist = (
        ".png",
        ".jpg",
        ".gif",
        ".jpeg",
    )
    if extension in ext_whitelist:
        return content_type, extension
    return None, None


def find_data(html, key):
    elements = html.select(f'meta[property="{key}"], meta[name="{key}"]')
    if elements:
        return elements[0].attrs.get("content")


def store_image(response, world):  # TODO deduplicate
    content_type, extension = get_extension_from_response(response)
    if not extension:
        return

    max_size = 10 * 1024 * 1024
    if not len(response.content) < max_size:
        return

    uid = uuid.uuid4()
    filename = f"{uid}{extension}"
    stored_file = StoredFile.objects.create(
        id=uid,
        world=world,
        date=now(),
        filename=filename,
        type=content_type,
        public=True,
        source_url=response.url[:254],
    )
    stored_file.file.save(filename, ContentFile(response.content))
    return stored_file.file.url


def retrieve_url(url):
    response = requests.get(url, timeout=10)  # TODO: user agent
    if response.status_code == 200:
        return response


def fetch_preview_data(url, world):
    """
    Fetches data from an external URL, and handles social media tags or their fallbacks,
    if any. If the URL refers to an image or the social tags include a preview image,
    the image is prefetched.

    The response format is a dictionary, including these keys (all optional):

    - url: Extracted from og:url, falling back to the original URL
    - title: Extracted from og:title, falling back to <title>
    - description: Extracted from og:description, falling back to description
    - format: Extracted from twitter:card, one of “summary”, “summary_large_image”, “app”, or “player”
    - image: a URL, extracted and cached from og:image
    - video: a video URL, extracted from og:video
    """

    response = retrieve_url(url)
    if not response:
        return
    content_type = response.headers.get("Content-Type", "text/html")  # Assume HTML

    if "image/" in content_type:
        image_url = store_image(response, world)
        if image_url:  # We don't store huge images
            return {"image": image_url}

    elif "text/html" in content_type:
        text = response.content.decode()
        header_end = text.find("</head>")
        if not header_end:  # Avoid parsing huge HTML docs for now
            return
        try:
            html = BeautifulSoup(text[: header_end + 7], "html.parser")
        except Exception:  # Ignore faulty websites
            return

        result = {}
        title = find_data(html, "og:title") or find_data(html, "title")
        if not title and html.find("title"):
            title = html.find("title").text
        if title:
            result["title"] = title
        result["description"] = find_data(html, "og:description") or find_data(
            html, "description"
        )
        result["format"] = find_data(html, "twitter:card")
        result["video"] = find_data(html, "og:video")

        result = {key: value for key, value in result.items() if value}

        image = find_data(html, "og:image")
        if image:
            response = retrieve_url(image)
            if response:
                image_url = store_image(response, world)
                if image_url:  # We don't store huge images
                    result["image"] = image_url

        if result:
            result["url"] = find_data(html, "og:url") or url

        return result or None
