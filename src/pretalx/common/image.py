from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageOps
from PIL.Image import Resampling

THUMBNAIL_SIZES = {
    "tiny": (64, 64),
    "default": (460, 460),
}


def process_image(*, image, generate_thumbnail=False):
    """
    This function receives an image that has been uploaded, and processes it
    by reducing its file size and stripping its metadata.
    Image must be an ImageFieldFile, e.g. user.avatar.
    """
    try:
        img = Image.open(image)
    except Exception:
        return

    extension = ".jpg"
    if img.mode.lower() in ("rgba", "la", "pa"):
        extension = ".png"
    elif img.mode != "RGB":
        img = img.convert("RGB")

    img_without_exif = Image.new(img.mode, img.size)
    img_without_exif.putdata(img.getdata())
    max_dimensions = (
        settings.IMAGE_DEFAULT_MAX_WIDTH,
        settings.IMAGE_DEFAULT_MAX_HEIGHT,
    )
    img_without_exif = ImageOps.exif_transpose(img_without_exif)
    img_without_exif.thumbnail(max_dimensions, resample=Resampling.LANCZOS)

    # Overwrite the original image with the processed one
    img_without_exif.save(image.path, quality="web_high" if extension == ".jpg" else 95)

    if generate_thumbnail:
        for size in THUMBNAIL_SIZES:
            create_thumbnail(image, size)


def get_thumbnail_field_name(image, size):
    thumbnail_field_name = f"{image.field.name}_thumbnail"
    if size != "default":
        thumbnail_field_name += f"_{size}"
    return thumbnail_field_name


def create_thumbnail(image, size):
    if size not in THUMBNAIL_SIZES:
        return
    thumbnail_field_name = get_thumbnail_field_name(image, size)
    if not image.instance._meta.get_field(thumbnail_field_name):
        return

    try:
        img = Image.open(image, formats=("PNG", "JPEG", "GIF"))
        img.load()
    except Exception:
        return None
    img.thumbnail(THUMBNAIL_SIZES[size], resample=Resampling.LANCZOS)
    thumbnail_field = getattr(image.instance, thumbnail_field_name)
    thumbnail_name = (
        Path(image.name).stem + f"_thumbnail_{size}" + Path(image.name).suffix
    )
    # Write the image to a BytesIO object
    img_byte_array = BytesIO()
    img.save(img_byte_array, format=img.format)
    thumbnail_field.save(
        thumbnail_name,
        ContentFile(img_byte_array.getvalue()),
    )
    return thumbnail_field


def get_thumbnail(image, size):
    thumbnail_field_name = get_thumbnail_field_name(image, size)
    if not (image.instance._meta.get_field(thumbnail_field_name)):
        return image

    thumbnail_field = getattr(image.instance, thumbnail_field_name)
    if not thumbnail_field or not thumbnail_field.storage.exists(thumbnail_field.path):
        return create_thumbnail(image, size)
    return thumbnail_field
