import json
import logging
from urllib.parse import urljoin

from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

register = template.Library()
LOGGER = logging.getLogger(__name__)
_MANIFEST = {}
MANIFEST_PATH = settings.STATIC_ROOT / "pretalx-manifest.json"

# We're building the manifest if we don't have a dev server running AND if we're
# not currently running `rebuild` (which creates the manifest in the first place).
if not settings.VITE_DEV_MODE and not settings.VITE_IGNORE:
    try:
        with open(MANIFEST_PATH) as fp:
            _MANIFEST = json.load(fp)
    except Exception as e:
        LOGGER.warning(f"Error reading vite manifest at {MANIFEST_PATH}: {str(e)}")


def generate_script_tag(path, attrs):
    all_attrs = " ".join(f'{key}="{value}"' for key, value in attrs.items())
    if settings.VITE_DEV_MODE:
        src = urljoin(settings.VITE_DEV_SERVER, path)
    else:
        src = urljoin(settings.STATIC_URL, path)
    return f'<script {all_attrs} src="{src}"></script>'


def generate_css_tags(asset, already_processed=None):
    """Recursively builds all CSS tags used in a given asset.

    Ignore the side effects."""
    tags = []
    manifest_entry = _MANIFEST[asset]
    if already_processed is None:
        already_processed = []

    # Put our own CSS file first for specificity
    if "css" in manifest_entry:
        for css_path in manifest_entry["css"]:
            if css_path not in already_processed:
                full_path = urljoin(settings.STATIC_URL, css_path)
                tags.append(f'<link rel="stylesheet" href="{full_path}" />')
            already_processed.append(css_path)

    # Import each file only one by way of side effects in already_processed
    if "imports" in manifest_entry:
        for import_path in manifest_entry["imports"]:
            tags += generate_css_tags(import_path, already_processed)

    return tags


@register.simple_tag
@mark_safe
def vite_asset(path):
    """
    Generates one <script> tag and <link> tags for each of the CSS dependencies.
    """

    if not path:
        return ""

    if settings.VITE_DEV_MODE:
        return generate_script_tag(path, {"type": "module"})

    manifest_entry = _MANIFEST.get(path)
    if not manifest_entry:
        raise RuntimeError(f"Cannot find {path} in Vite manifest at {MANIFEST_PATH}")

    tags = generate_css_tags(path)
    tags.append(
        generate_script_tag(
            manifest_entry["file"], {"type": "module", "crossorigin": ""}
        )
    )
    return "".join(tags)


@register.simple_tag
@mark_safe
def vite_hmr():
    if not settings.VITE_DEV_MODE:
        return ""
    return generate_script_tag("@vite/client", {"type": "module"})
