import io
import pytest
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from eventyay.base.models import User


def create_test_image_file():
    file = io.BytesIO()
    image = Image.new('RGB', (200, 200), color='blue')
    image.save(file, 'PNG')
    file.seek(0)
    return SimpleUploadedFile('test_profile_picture.png', file.read(), content_type='image/png')


@pytest.mark.django_db
def test_user_account_settings_view_get(client):
    user = User.objects.create_user(email='profile_pic_test@example.com', password='password123')
    client.force_login(user)

    response = client.get(reverse('eventyay_common:account.general'))
    assert response.status_code == 200
    assert 'Profile picture' in response.content.decode('utf-8')
    assert 'name="profile_picture"' in response.content.decode('utf-8')


@pytest.mark.django_db
def test_user_account_profile_picture_upload(client):
    user = User.objects.create_user(email='profile_pic_upload@example.com', password='password123')
    client.force_login(user)

    image_file = create_test_image_file()

    response = client.post(
        reverse('eventyay_common:account.general'),
        {
            'fullname': 'Profile Picture User',
            'locale': 'en',
            'timezone': 'UTC',
            'profile_picture': image_file,
        },
        follow=True,
    )
    assert response.status_code == 200

    user.refresh_from_db()
    assert bool(user.profile_picture) is True
    assert user.get_profile_picture_url() != ''
    assert 'profile_pictures/' in user.profile_picture.name


@pytest.mark.django_db
def test_user_account_profile_picture_crop_tolerance(client):
    user = User.objects.create_user(email='profile_pic_crop@example.com', password='password123')
    client.force_login(user)

    image_file = create_test_image_file()

    response = client.post(
        reverse('eventyay_common:account.general'),
        {
            'fullname': 'Profile Picture User',
            'locale': 'en',
            'timezone': 'UTC',
            'profile_picture': image_file,
            'profile_picture_crop_x': '0',
            'profile_picture_crop_y': '0',
            'profile_picture_crop_w': '200.5',
            'profile_picture_crop_h': '201.5',
        },
        follow=True,
    )
    assert response.status_code == 200

    user.refresh_from_db()
    assert bool(user.profile_picture) is True
    assert user.get_profile_picture_url() != ''
    assert 'profile_pictures/' in user.profile_picture.name


@pytest.mark.django_db
def test_user_account_clear_profile_picture(client):
    user = User.objects.create_user(email='profile_pic_clear@example.com', password='password123')
    client.force_login(user)

    # First upload a profile picture
    image_file = create_test_image_file()
    client.post(
        reverse('eventyay_common:account.general'),
        {
            'fullname': 'Profile Picture User',
            'locale': 'en',
            'timezone': 'UTC',
            'profile_picture': image_file,
        },
    )
    user.refresh_from_db()
    assert bool(user.profile_picture) is True
    pic_name = user.profile_picture.name
    pic_storage = user.profile_picture.storage
    assert pic_storage.exists(pic_name)

    thumb_name = user.profile_picture_thumbnail.name if user.profile_picture_thumbnail else None
    thumb_storage = user.profile_picture_thumbnail.storage if user.profile_picture_thumbnail else None
    tiny_thumb_name = user.profile_picture_thumbnail_tiny.name if user.profile_picture_thumbnail_tiny else None
    tiny_thumb_storage = user.profile_picture_thumbnail_tiny.storage if user.profile_picture_thumbnail_tiny else None

    # Now clear the profile picture
    response = client.post(
        reverse('eventyay_common:account.general'),
        {
            'fullname': 'Profile Picture User',
            'locale': 'en',
            'timezone': 'UTC',
            'clear_profile_picture': 'on',
        },
        follow=True,
    )
    assert response.status_code == 200

    user.refresh_from_db()
    assert bool(user.profile_picture) is False
    assert not user.profile_picture_thumbnail
    assert not user.profile_picture_thumbnail_tiny
    assert not pic_storage.exists(pic_name)
    if thumb_name and thumb_storage:
        assert not thumb_storage.exists(thumb_name)
    if tiny_thumb_name and tiny_thumb_storage:
        assert not tiny_thumb_storage.exists(tiny_thumb_name)


@pytest.mark.django_db
def test_user_account_profile_picture_and_clear_conflict(client):
    user = User.objects.create_user(email='profile_pic_conflict@example.com', password='password123')
    client.force_login(user)

    image_file = create_test_image_file()
    response = client.post(
        reverse('eventyay_common:account.general'),
        {
            'fullname': 'Profile Picture User',
            'locale': 'en',
            'timezone': 'UTC',
            'profile_picture': image_file,
            'clear_profile_picture': 'on',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'Cannot upload a new profile picture and remove the existing one at the same time.' in response.content.decode('utf-8')


@pytest.mark.django_db
def test_user_account_clear_profile_picture_with_existing_no_conflict(client):
    user = User.objects.create_user(email='profile_pic_no_conflict@example.com', password='password123')
    client.force_login(user)

    # 1. Upload initial profile picture
    image_file = create_test_image_file()
    client.post(
        reverse('eventyay_common:account.general'),
        {
            'fullname': 'Profile Picture User',
            'locale': 'en',
            'timezone': 'UTC',
            'profile_picture': image_file,
        },
        follow=True,
    )
    user.refresh_from_db()
    assert bool(user.profile_picture) is True

    # 2. Check clear_profile_picture without uploading a new file -> should succeed without conflict
    response = client.post(
        reverse('eventyay_common:account.general'),
        {
            'fullname': 'Profile Picture User',
            'locale': 'en',
            'timezone': 'UTC',
            'clear_profile_picture': 'on',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'Cannot upload a new profile picture' not in response.content.decode('utf-8')
    user.refresh_from_db()
    assert bool(user.profile_picture) is False
