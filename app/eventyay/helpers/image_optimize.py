"""
Image optimization helpers for event logo and header image uploads.

Uploaded images are resized to a maximum width on save so that public pages
never serve the original, potentially multi-megabyte file.  The original is
always preserved alongside the optimized version so that organisers can
re-crop or reprocess it in a future release.

Usage::

    from eventyay.helpers.image_optimize import optimize_uploaded_image

    result = optimize_uploaded_image(
        uploaded_file,
        setting_key='logo_image',   # 'logo_image' or 'event_logo_image'
    )
    # Save `result.optimized` to storage; `result.original` can be stored at a sibling path.
"""

from __future__ import annotations

import logging
import os
import warnings
from io import BytesIO
from typing import NamedTuple

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from PIL import Image, ImageOps
from PIL.Image import DecompressionBombError, DecompressionBombWarning

from eventyay.common.image import encode_optimized

logger = logging.getLogger(__name__)

# Maximum output width per asset type.  Height is always proportional.
MAX_WIDTH: dict[str, int] = {
    'logo_image': 1920,       # header/banner image
    'event_logo_image': 1000, # event logo
    'event_preview_image': 1200, # event preview card image
    'organizer_logo_image': 1000,
    'organizer_header_image': 1920,
    'og_image': 1200,            # social media image
    'picture': 1000,             # product/room picture
    'invoice_logo_image': 1000,
    'startpage_header_image': 1920,
    'profile_picture': 1000,     # user profile picture
}

class OptimizedImages(NamedTuple):
    """Pair of ContentFile objects returned by optimize_uploaded_image."""

    optimized: ContentFile
    """The resized/recompressed file that should be stored and served."""

    original: ContentFile
    """The untouched original bytes, stored for future re-processing."""

    optimized_ext: str
    """File extension (without leading dot) for the optimized file."""

    original_ext: str
    """File extension (without leading dot) for the original file."""

# Removed _has_alpha and _encode_optimized in favor of eventyay.common.image.encode_optimized


def optimize_uploaded_image(
    uploaded: UploadedFile,
    setting_key: str,
    crop_box: tuple[int, int, int, int] | None = None,
) -> OptimizedImages:
    """
    Resize *uploaded* to the cap for *setting_key* and return both the
    optimized and the original as ``ContentFile`` objects.

    If the image is already within the maximum width it is still re-encoded
    to ensure consistent output format, but its dimensions are not changed.

    Raises ``ValueError`` for unknown *setting_key* values.
    Raises ``OSError`` / ``PIL.UnidentifiedImageError`` when the file cannot
    be decoded as an image.
    """
    if setting_key not in MAX_WIDTH:
        raise ValueError('Unknown image setting key: %s' % setting_key)

    max_w = MAX_WIDTH[setting_key]

    if hasattr(uploaded, 'seek'):
        uploaded.seek(0)
    raw = uploaded.read()
    if hasattr(uploaded, 'seek'):
        uploaded.seek(0)

    _, original_ext = os.path.splitext(uploaded.name or 'upload')
    original_ext = (original_ext.lstrip('.') or 'jpg').lower()

    if original_ext == 'svg':
        logger.info('Bypassing optimization for SVG image')
        return OptimizedImages(
            optimized=ContentFile(raw),
            original=ContentFile(raw),
            optimized_ext='svg',
            original_ext='svg',
        )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', DecompressionBombWarning)
            image = Image.open(BytesIO(raw))
            image.load()
    except (DecompressionBombError, DecompressionBombWarning) as e:
        logger.exception('Image too large to load (DecompressionBombError)')
        raise ValueError('Image exceeds maximum safe dimensions') from e
    except OSError:
        logger.exception('Could not load uploaded image for optimization')
        raise

    is_animated = getattr(image, 'is_animated', False)
    if is_animated:
        ext = image.format.lower() if image.format else original_ext
        logger.info('Bypassing optimization for animated %s image', ext)
        return OptimizedImages(
            optimized=ContentFile(raw),
            original=ContentFile(raw),
            optimized_ext=ext,
            original_ext=original_ext,
        )

    image = ImageOps.exif_transpose(image)

    if crop_box:
        left, top, right, bottom = crop_box
        if 0 <= left < right <= image.width and 0 <= top < bottom <= image.height:
            logger.info('Cropping %s to %s', setting_key, crop_box)
            image = image.crop(crop_box)
        else:
            logger.warning(
                'Crop box %s out of image bounds (%sx%s); ignoring crop box',
                crop_box,
                image.width,
                image.height,
            )

    orig_w, _ = image.size
    
    optimized_bytes, optimized_ext = encode_optimized(image, f'.{original_ext}', max_dimensions=(max_w, 999999))
    
    # encode_optimized returns extensions with a dot (e.g., '.jpg')
    optimized_ext = optimized_ext.lstrip('.')
    
    original_ext_norm = 'jpg' if original_ext in ('jpg', 'jpeg') else original_ext
    
    # Prevent PNG/WebP size growth: if we didn't crop or resize, and format didn't change
    if not crop_box and orig_w <= max_w and len(optimized_bytes) >= len(raw) and optimized_ext == original_ext_norm:
        optimized_bytes = raw
        
    optimized_file = ContentFile(optimized_bytes)
    original_file = ContentFile(raw)

    return OptimizedImages(
        optimized=optimized_file,
        original=original_file,
        optimized_ext=optimized_ext,
        original_ext=original_ext,
    )
