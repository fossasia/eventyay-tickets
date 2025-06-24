import tempfile

import pytest
from django.core.files.base import ContentFile

from pretalx.common.models.file import CachedFile


@pytest.mark.django_db
def test_upload_file(client, orga_user_token):
    assert CachedFile.objects.all().count() == 0
    with tempfile.NamedTemporaryFile(suffix=".pdf") as upload_file:
        upload_file.write(b"invalid pdf content")
        upload_file.seek(0)
        response = client.post(
            "/api/upload/",
            data={"name": "file.pdf", "file_field": ContentFile("invalid pdf content")},
            headers={
                "Authorization": f"Token {orga_user_token.token}",
                "Content-Disposition": 'attachment; filename="file.pdf"',
                "Content-Type": "application/pdf",
            },
        )
    assert response.status_code == 201, response.text
    assert response.data["id"].startswith("file:")
    assert CachedFile.objects.all().count() == 1


@pytest.mark.django_db
def test_upload_file_extension_mismatch(client, orga_user_token):
    with tempfile.NamedTemporaryFile(suffix=".pdf") as upload_file:
        upload_file.write(b"invalid pdf content")
        upload_file.seek(0)
        response = client.post(
            "/api/upload/",
            data={"name": "file.png", "file_field": ContentFile("invalid pdf content")},
            headers={
                "Authorization": f"Token {orga_user_token.token}",
                "Content-Disposition": 'attachment; filename="file.png"',
                "Content-Type": "application/pdf",
            },
        )
    assert response.status_code == 400
    assert response.data == [
        'File name "file.png" has an invalid extension for type "application/pdf"'
    ]


@pytest.mark.django_db
def test_upload_file_extension_not_allowed(client, orga_user_token):
    with tempfile.NamedTemporaryFile(suffix=".bin") as upload_file:
        upload_file.write(b"invalid pdf content")
        upload_file.seek(0)
        response = client.post(
            "/api/upload/",
            data={"name": "file.bin", "file_field": ContentFile("invalid pdf content")},
            headers={
                "Authorization": f"Token {orga_user_token.token}",
                "Content-Disposition": 'attachment; filename="file.png"',
                "Content-Type": "application/octet-stream",
            },
        )
    assert response.status_code == 400
    assert "Content type is not allowed" in str(response.data)
