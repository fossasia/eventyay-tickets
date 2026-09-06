import logging
import os
import re
import tempfile
from functools import partial
from io import BytesIO
from pathlib import Path

from csp.decorators import csp_update
from defusedxml import ElementTree as DefusedElementTree
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils.translation import gettext_lazy as _
from PIL import Image, ImageOps
from PIL.Image import MAX_IMAGE_PIXELS, DecompressionBombError, Resampling

from eventyay.common.templatetags.filesize import filesize

logger = logging.getLogger(__name__)

THUMBNAIL_SIZES = {
    'tiny': (64, 64),
    'default': (460, 460),
}

IMAGE_EXTENSIONS = {
    '.png': ['image/png', '.png'],
    '.jpg': ['image/jpeg', '.jpg'],
    '.jpeg': ['image/jpeg', '.jpeg'],
    '.gif': ['image/gif', '.gif'],
    '.svg': ['image/svg+xml', '.svg'],
    '.webp': ['image/webp', '.webp'],
}

ALLOWED_IMAGE_EXTENSIONS = frozenset(IMAGE_EXTENSIONS)

RASTER_THUMBNAIL_FORMATS = ('PNG', 'JPEG', 'GIF', 'WEBP')

REWRITABLE_ORIGINAL_EXTENSIONS = frozenset({'.jpg', '.jpeg', '.png', '.webp'})

FORBIDDEN_SVG_TAGS = frozenset(
    {
        'script',
        'foreignobject',
        'iframe',
        'embed',
        'object',
        'audio',
        'video',
    }
)

AVATAR_THUMBNAIL_FIELDS = ('avatar_thumbnail', 'avatar_thumbnail_tiny')


def thumbnail_matches_avatar(avatar_name, thumbnail_name, size):
    if not avatar_name or not thumbnail_name or size not in THUMBNAIL_SIZES:
        return False
    if str(avatar_name).lower().endswith('.svg'):
        return False
    avatar_path = Path(avatar_name)
    thumbnail_path = Path(thumbnail_name)
    return thumbnail_path.stem == f'{avatar_path.stem}_thumbnail_{size}'


def clear_avatar_thumbnails(instance):
    """Delete raster thumbnail files when the main avatar is replaced or removed."""
    for field_name in AVATAR_THUMBNAIL_FIELDS:
        thumbnail = getattr(instance, field_name, None)
        if thumbnail:
            thumbnail.delete(save=False)
        setattr(instance, field_name, None)


def invalidate_speaker_avatar_caches(user):
    """Drop cached speaker schedule JSON after avatar URLs may have changed."""
    if not user.code:
        return

    from eventyay.agenda.views.utils import clear_schedule_caches
    from eventyay.base.models import Event
    from eventyay.base.models.profile import SpeakerProfile
    from django_scopes import scopes_disabled

    with scopes_disabled():
        event_ids = list(SpeakerProfile.objects.filter(user_id=user.pk).values_list('event_id', flat=True))
        events = list(Event.objects.filter(pk__in=event_ids))

    for event in events:
        clear_schedule_caches(event, speaker=user)

gravatar_csp = partial(
    csp_update,
    {
        'IMG_SRC': 'https://www.gravatar.com',
        'CONNECT_SRC': 'https://www.gravatar.com',
    },
)


def is_svg_filename(filename):
    return str(filename).lower().endswith('.svg')


def _read_uploaded_file(f):
    if hasattr(f, 'temporary_file_path'):
        with open(f.temporary_file_path(), 'rb') as uploaded:
            return uploaded.read()
    if hasattr(f, 'read'):
        if hasattr(f, 'seek') and callable(f.seek):
            f.seek(0)
        content = f.read()
        if hasattr(f, 'seek') and callable(f.seek):
            f.seek(0)
        return content
    return f['content']


def _svg_local_tag(tag):
    return tag.rsplit('}', 1)[-1].lower()


def _validate_svg_content(content):
    max_size = getattr(settings, 'IMAGE_SVG_MAX_SIZE', 1024 * 1024)
    if len(content) > max_size:
        raise ValidationError(
            _('SVG files must be smaller than {size}. Please simplify the image or upload a PNG/JPEG instead.').format(
                size=filesize(max_size),
            )
        )

    lowered = content.lower()
    if b'<script' in lowered or b'javascript:' in lowered:
        raise ValidationError(_('This SVG file contains disallowed content and cannot be uploaded.'))

    try:
        root = DefusedElementTree.fromstring(content)
    except DefusedElementTree.ParseError as exc:
        raise ValidationError(
            _('Upload a valid SVG image. The file you uploaded was either not an SVG or a corrupted SVG.')
        ) from exc

    if _svg_local_tag(root.tag) != 'svg':
        raise ValidationError(
            _('Upload a valid SVG image. The file you uploaded was either not an SVG or a corrupted SVG.')
        )

    for element in root.iter():
        if _svg_local_tag(element.tag) in FORBIDDEN_SVG_TAGS:
            raise ValidationError(_('This SVG file contains disallowed content and cannot be uploaded.'))
        for attr_name, attr_value in element.attrib.items():
            attr_name_lower = _svg_local_tag(attr_name)
            if attr_name_lower.startswith('on'):
                raise ValidationError(_('This SVG file contains disallowed content and cannot be uploaded.'))
            if attr_name_lower in {'href', 'src', 'xlink:href'} and re.match(
                r'^\s*(javascript|data):', attr_value, flags=re.IGNORECASE
            ):
                raise ValidationError(_('This SVG file contains disallowed content and cannot be uploaded.'))


def validate_image(f):
    if f is None:
        return None

    filename = getattr(f, 'name', '')
    if is_svg_filename(filename):
        _validate_svg_content(_read_uploaded_file(f))
        return

    if hasattr(f, 'temporary_file_path'):
        file = f.temporary_file_path()
    elif hasattr(f, 'read'):
        if hasattr(f, 'seek') and callable(f.seek):
            f.seek(0)
        file = BytesIO(f.read())
    else:
        file = BytesIO(f['content'])

    try:
        try:
            formats = getattr(settings, 'PILLOW_FORMATS_QUESTIONS_IMAGE', None) or RASTER_THUMBNAIL_FORMATS
            image = Image.open(file, formats=formats)
            # verify() must be called immediately after the constructor.
            image.verify()
        except DecompressionBombError:
            raise ValidationError(
                _(
                    'The file you uploaded has a very large number of pixels, please upload a picture with '
                    'smaller dimensions.'
                )
            )

        # load() is a potential DoS vector (see Django bug #18520), so we verify the size first
        if image.width * image.height > MAX_IMAGE_PIXELS:
            raise ValidationError(
                _(
                    'The file you uploaded has a very large number of pixels, please upload a picture with '
                    'smaller dimensions.'
                )
            )
    except Exception as exc:
        if isinstance(exc, ValidationError):
            raise
        raise ValidationError(
            _('Upload a valid image. The file you uploaded was either not an image or a corrupted image.')
        ) from exc
    if hasattr(f, 'seek') and callable(f.seek):
        f.seek(0)


def _open_raster_image(image):
    try:
        path = getattr(image, 'path', None)
    except (NotImplementedError, AttributeError):
        path = None

    if path:
        opened = Image.open(path)
        opened.load()
        return opened

    file_obj = image.open('rb')
    try:
        opened = Image.open(file_obj)
        opened.load()
        return opened
    finally:
        file_obj.close()


def _has_alpha(image: Image.Image) -> bool:
    return image.mode in ('RGBA', 'LA', 'PA') or (
        image.mode == 'P' and 'transparency' in image.info
    )


def encode_optimized(img, original_ext, max_dimensions=None, keep_format=False):
    """
    Strips EXIF, resizes to max_dimensions, and encodes to optimal format.
    Returns (data_bytes, extension).
    """
    if max_dimensions is None:
        max_dimensions = (
            settings.IMAGE_DEFAULT_MAX_WIDTH,
            settings.IMAGE_DEFAULT_MAX_HEIGHT,
        )
        
    img = ImageOps.exif_transpose(img)
    
    # Strip EXIF by pasting into a new image
    mode = img.mode
    if _has_alpha(img):
        mode = 'RGBA'
    elif mode not in ('RGB', 'L'):
        mode = 'RGB'
        
    img_without_exif = Image.new(mode, img.size)
    img_without_exif.paste(img)
    
    orig_w, orig_h = img_without_exif.size
    max_w, max_h = max_dimensions
    
    # Resize preserving aspect ratio (thumbnail modifies in place)
    if orig_w > max_w or orig_h > max_h:
        img_without_exif.thumbnail(max_dimensions, resample=Resampling.LANCZOS)
    
    buf = BytesIO()
    original_ext = original_ext.lower()
    
    if _has_alpha(img_without_exif):
        if original_ext == '.webp':
            img_without_exif.save(buf, format='WEBP', quality=75)
            return buf.getvalue(), '.webp'
        else:
            img_without_exif.save(buf, format='PNG', optimize=True)
            return buf.getvalue(), '.png'
    else:
        if keep_format and original_ext == '.png':
            img_without_exif.save(buf, format='PNG', optimize=True)
            return buf.getvalue(), '.png'
        elif original_ext == '.webp':
            img_without_exif.save(buf, format='WEBP', quality=75)
            return buf.getvalue(), '.webp'
        else:
            if img_without_exif.mode != 'RGB':
                img_without_exif = img_without_exif.convert('RGB')
            img_without_exif.save(buf, format='JPEG', quality=70, progressive=True, optimize=True)
            return buf.getvalue(), '.jpg'



def _generate_thumbnails(image):
    for size in THUMBNAIL_SIZES:
        create_thumbnail(image, size)


def process_image(*, image, generate_thumbnail=False):
    """
    This function receives an image that has been uploaded, and processes it
    by reducing its file size and stripping its metadata.
    Image must be an ImageFieldFile, e.g. user.avatar.

    Returns True when processing completed (including intentional skips such as
    animated GIF originals), False when the image could not be processed.
    """
    if is_svg_filename(image.name):
        return True

    try:
        img = _open_raster_image(image)
    except Exception:
        logger.exception('Failed to process image %s', getattr(image, 'name', image))
        return False

    if getattr(img, 'is_animated', False):
        if generate_thumbnail:
            _generate_thumbnails(image)
        return True

    extension = Path(image.name).suffix.lower()
    if extension == '.jpeg':
        extension = '.jpg'
    if extension not in REWRITABLE_ORIGINAL_EXTENSIONS:
        if generate_thumbnail:
            _generate_thumbnails(image)
        return True

    try:
        try:
            original_size = image.size
        except (NotImplementedError, AttributeError, OSError):
            original_size = 0
            
        optimized_bytes, new_extension = encode_optimized(img, extension, keep_format=True)
        
        if original_size > 0 and len(optimized_bytes) >= original_size and extension == new_extension:
            # Prevent PNG/WebP size growth: if the new file is larger and format is identical, keep original
            pass
        else:
            # We need to overwrite
            buf = BytesIO(optimized_bytes)
            
            local_path = None
            try:
                local_path = image.path
            except (NotImplementedError, AttributeError):
                pass
    
            if local_path:
                # Attempt atomic local file replacement
                dir_name = os.path.dirname(local_path)
                temp_path = None
                try:
                    fd, temp_path = tempfile.mkstemp(dir=dir_name, suffix=extension)
                    with os.fdopen(fd, 'wb') as temp_f:
                        temp_f.write(buf.getvalue())
                    
                    os.chmod(temp_path, os.stat(local_path).st_mode)
                    os.replace(temp_path, local_path)
                    temp_path = None
                finally:
                    if temp_path is not None:
                        try:
                            os.unlink(temp_path)
                        except OSError:
                            pass
            else:
                # Fallback for remote storage backends (e.g., S3)
                original_name = image.name
                
                # 1. Save new file (may generate a new name or overwrite depending on storage)
                final_name = image.storage.save(original_name, ContentFile(buf.getvalue()))
                
                # 2. If a new name was generated, update the database and delete the old file
                if final_name != original_name:
                    image.name = final_name
                    if getattr(image, 'instance', None) is not None and getattr(image, 'field', None) is not None:
                        image.instance.save(update_fields=[image.field.name])
                    try:
                        image.storage.delete(original_name)
                    except OSError:
                        pass
            
    except (OSError, ValueError, DecompressionBombError, AttributeError, NotImplementedError):
        logger.exception('Failed to save processed image %s', getattr(image, 'name', image))
        return False

    if generate_thumbnail:
        _generate_thumbnails(image)
    return True


def get_thumbnail_field_name(image, size):
    thumbnail_field_name = f'{image.field.name}_thumbnail'
    if size != 'default':
        thumbnail_field_name += f'_{size}'
    return thumbnail_field_name


def create_thumbnail(image, size):
    if size not in THUMBNAIL_SIZES:
        return
    thumbnail_field_name = get_thumbnail_field_name(image, size)
    if not image.instance._meta.get_field(thumbnail_field_name):
        return

    if is_svg_filename(image.name):
        return None

    try:
        img = _open_raster_image(image)
    except Exception:
        logger.exception('Thumbnail creation failed for %s', getattr(image, 'name', image))

        return None
    img.thumbnail(THUMBNAIL_SIZES[size], resample=Resampling.LANCZOS)
    thumbnail_field = getattr(image.instance, thumbnail_field_name)

    extension = '.jpg'
    save_format = 'JPEG'
    save_kwargs = {'quality': 80, 'progressive': True, 'optimize': True}

    if img.mode.lower() in ('rgba', 'la', 'pa'):
        extension = '.png'
        save_format = 'PNG'
        save_kwargs = {'optimize': True}
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    thumbnail_name = Path(image.name).stem + f'_thumbnail_{size}' + extension
    # Write the image to a BytesIO object
    img_byte_array = BytesIO()
    img.save(img_byte_array, format=save_format, **save_kwargs)
    thumbnail_field.save(
        thumbnail_name,
        ContentFile(img_byte_array.getvalue()),
    )
    return thumbnail_field


def recompress_image_field(image, *, generate_thumbnail=False):
    """
    Re-run raster compression and optional thumbnail generation in-place.

    Returns True when the file was processed, False when skipped or failed.
    """
    if not image or not getattr(image, 'name', None):
        return False
    if is_svg_filename(image.name):
        return False

    try:
        size = image.size
    except Exception:
        logger.exception('Could not read size for image %s', image.name)
        return False

    if not getattr(image, 'path', None):
        logger.warning('Skipping in-place compression for remote-only image %s', image.name)
        return False

    processed = process_image(image=image, generate_thumbnail=generate_thumbnail)
    if not processed:
        logger.error('Failed to recompress image %s', image.name)
        return False

    try:
        new_size = image.size
    except Exception:
        new_size = None

    size_kb = f'{size / 1024:.2f} KB'
    new_size_kb = f'{new_size / 1024:.2f} KB' if isinstance(new_size, int) else 'unknown'

    logger.info(
        'Recompressed image %s (%s -> %s)',
        image.name,
        size_kb,
        new_size_kb,
    )
    return True


def get_thumbnail(image, size):
    thumbnail_field_name = get_thumbnail_field_name(image, size)
    if not (image.instance._meta.get_field(thumbnail_field_name)):
        return image

    if is_svg_filename(image.name):
        return image

    thumbnail_field = getattr(image.instance, thumbnail_field_name)
    if thumbnail_field and thumbnail_field.name:
        if not thumbnail_matches_avatar(image.name, thumbnail_field.name, size):
            thumbnail_field.delete(save=False)
            setattr(image.instance, thumbnail_field_name, None)
            thumbnail_field = None
        elif not thumbnail_field.storage.exists(thumbnail_field.name):
            thumbnail_field = None
    if not thumbnail_field:
        return create_thumbnail(image, size)
    return thumbnail_field
