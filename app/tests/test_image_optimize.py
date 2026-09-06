from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from eventyay.helpers.image_optimize import (
    MAX_WIDTH,
    OptimizedImages,
    optimize_uploaded_image,
)


def _create_test_image(width: int, height: int, mode: str = 'RGB', format: str = 'JPEG') -> SimpleUploadedFile:
    img = Image.new(mode, (width, height), color='red')
    buf = BytesIO()
    img.save(buf, format=format)
    buf.seek(0)
    return SimpleUploadedFile(
        name=f'test.{format.lower()}',
        content=buf.read(),
        content_type=f'image/{format.lower()}',
    )


@pytest.mark.parametrize('setting_key', ['logo_image', 'event_logo_image', 'event_preview_image', 'organizer_logo_image', 'organizer_header_image', 'og_image', 'picture'])
def test_optimize_uploaded_image_resizes(setting_key):
    max_w = MAX_WIDTH[setting_key]
    orig_w = max_w + 500
    orig_h = max_w

    upload = _create_test_image(orig_w, orig_h)
    result = optimize_uploaded_image(upload, setting_key)

    assert isinstance(result, OptimizedImages)

    # Check optimized file
    opt_img = Image.open(result.optimized)
    assert opt_img.size[0] == max_w
    # height should scale proportionally, allow 1px rounding diff
    expected_h = int(orig_h * (max_w / orig_w))
    assert abs(opt_img.size[1] - expected_h) <= 1

    # Check original file
    orig_img = Image.open(result.original)
    assert orig_img.size == (orig_w, orig_h)

    # Extensions
    assert result.optimized_ext == 'jpg'
    assert result.original_ext == 'jpeg'


def test_optimize_uploaded_image_keeps_png_with_alpha():
    upload = _create_test_image(800, 600, mode='RGBA', format='PNG')
    result = optimize_uploaded_image(upload, 'event_logo_image')

    opt_img = Image.open(result.optimized)
    assert opt_img.format == 'PNG'
    assert result.optimized_ext == 'png'


def test_optimize_uploaded_image_converts_bmp_to_jpg():
    upload = _create_test_image(800, 600, mode='RGB', format='BMP')
    upload.name = 'test.bmp'
    result = optimize_uploaded_image(upload, 'logo_image')

    opt_img = Image.open(result.optimized)
    assert opt_img.format == 'JPEG'
    assert result.optimized_ext == 'jpg'
    assert result.original_ext == 'bmp'


def test_optimize_uploaded_image_invalid_key():
    upload = _create_test_image(100, 100)
    with pytest.raises(ValueError, match='Unknown image setting key'):
        optimize_uploaded_image(upload, 'invalid_key')


def test_optimize_uploaded_image_invalid_image():
    upload = SimpleUploadedFile(
        name='test.jpg',
        content=b'not an image file',
        content_type='image/jpeg',
    )
    with pytest.raises(OSError):
        optimize_uploaded_image(upload, 'logo_image')


def test_optimize_uploaded_image_preserves_animated_gif():
    # Create an animated GIF with width > MAX_WIDTH
    img1 = Image.new('RGB', (4000, 4000), 'red')
    img2 = Image.new('RGB', (4000, 4000), 'blue')
    buf = BytesIO()
    img1.save(buf, format='GIF', save_all=True, append_images=[img2], duration=100, loop=0)
    buf.seek(0)

    upload = SimpleUploadedFile(
        name='test.gif',
        content=buf.read(),
        content_type='image/gif',
    )

    result = optimize_uploaded_image(upload, 'logo_image')

    # Assert that the image was not resized, even though it's 4000x4000
    # and the max width for logo_image is 3000
    opt_img = Image.open(result.optimized)
    assert opt_img.size == (4000, 4000)
    assert getattr(opt_img, 'is_animated', False)
    assert result.optimized_ext == 'gif'

def test_optimize_uploaded_image_bypasses_svg():
    svg_content = b'<svg width="10" height="10"></svg>'
    upload = SimpleUploadedFile(
        name='test.svg',
        content=svg_content,
        content_type='image/svg+xml',
    )
    result = optimize_uploaded_image(upload, 'logo_image')
    assert result.optimized_ext == 'svg'
    assert result.original_ext == 'svg'
    assert result.optimized.read() == svg_content
    assert result.original.read() == svg_content
