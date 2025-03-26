import pytest
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError

# Constants for testing
VALID_PDF_CONTENT = 'valid pdf content'
INVALID_PDF_CONTENT = 'invalid pdf content'
LARGE_FILE_CONTENT = 'A' * (10 * 1024 * 1024)  # 10 MB file content
EMPTY_FILE_CONTENT = ''
MALICIOUS_FILE_CONTENT = '<?php echo "malicious"; ?>'  # Example of a malicious file content

@pytest.mark.django_db
def test_upload_file(token_client):
    r = token_client.post(
        '/api/v1/upload',
        data={
            'media_type': 'application/pdf',
            'file': ContentFile(VALID_PDF_CONTENT, 'file.pdf')
        },
        format='upload',
        HTTP_CONTENT_DISPOSITION='attachment; filename="file.pdf"',
    )
    assert r.status_code == 201
    assert r.data['id'].startswith('file:')

@pytest.mark.django_db
def test_upload_file_extension_mismatch(token_client):
    r = token_client.post(
        '/api/v1/upload',
        data={
            'media_type': 'application/pdf',
            'file': ContentFile('file.png', 'invalid pdf content')
        },
        format='upload',
        HTTP_CONTENT_DISPOSITION='attachment; filename="file.png"',
    )
    assert r.status_code == 400

# New test cases

@pytest.mark.django_db
def test_upload_large_file(token_client):
    r = token_client.post(
        '/api/v1/upload',
        data={
            'media_type': 'application/pdf',
            'file': ContentFile(LARGE_FILE_CONTENT, 'large_file.pdf')
        },
        format='upload',
        HTTP_CONTENT_DISPOSITION='attachment; filename="large_file.pdf"',
    )
    assert r.status_code == 201  # Assuming the server allows large files

@pytest.mark.django_db
def test_upload_empty_file(token_client):
    r = token_client.post(
        '/api/v1/upload',
        data={
            'media_type': 'application/pdf',
            'file': ContentFile(EMPTY_FILE_CONTENT, 'empty_file.pdf')
        },
        format='upload',
        HTTP_CONTENT_DISPOSITION='attachment; filename="empty_file.pdf"',
    )
    assert r.status_code == 400  # Expecting a bad request for empty file

@pytest.mark.django_db
def test_upload_multiple_files(token_client):
    files = [
        ContentFile(VALID_PDF_CONTENT, 'file1.pdf'),
        ContentFile(VALID_PDF_CONTENT, 'file2.pdf')
    ]
    r = token_client.post(
        '/api/v1/upload',
        data={
            'media_type': 'application/pdf',
            'file': files
        },
        format='upload',
    )
    assert r.status_code == 201  # Assuming the server supports multiple uploads

@pytest.mark.django_db
def test_unauthorized_upload(token_client):
    # Simulate an unauthorized request
    r = token_client.post(
        '/api/v1/upload',
        data={
            'media_type': 'application/pdf',
            'file': ContentFile(VALID_PDF_CONTENT, 'file.pdf')
        },
        format='upload',
    )
    assert r.status_code == 401  # Expecting unauthorized status

@pytest.mark.django_db
def test_mismatched_content_type(token_client):
    r = token_client.post(
        '/api/v1/upload',
        data={
            'media_type': 'application/pdf',
            'file': ContentFile(MALICIOUS_FILE_CONTENT, 'malicious.php')
        },
        format='upload',
        HTTP_CONTENT_DISPOSITION='attachment; filename="malicious.php"',
    )
    assert r.status_code == 400  # Expecting a bad request for mismatched content type

@pytest.mark.django_db
def test_duplicate_file_upload(token_client):
    # First upload
    r1 = token_client.post(
        '/api/v1/upload',
        data={
            'media_type': 'application/pdf',
            'file': ContentFile(VALID_PDF_CONTENT, 'duplicate_file.pdf')
        },
        format='upload',
        HTTP_CONTENT_DISPOSITION='attachment; filename="duplicate_file.pdf"',
    )
    assert r1.status_code == 201

    # Second upload with the same file
    r2 = token_client.post(
        '/api/v1/upload',
        data={
            'media_type': 'application/pdf',
            'file': ContentFile(VALID_PDF_CONTENT, 'duplicate_file.pdf')
        },
        format='upload',
        HTTP_CONTENT_DISPOSITION='attachment; filename="duplicate_file.pdf"',
    )
    assert r2.status_code == 409  # Expecting conflict for duplicate file

# Security tests
@pytest.mark.django_db
def test_malicious_file_upload(token_client):
    r = token_client.post(
        '/api/v1/upload',
        data={
            'media_type': 'application/x-php',
            'file': ContentFile(MALICIOUS_FILE_CONTENT, 'malicious.php')
        },
        format='upload',
        HTTP_CONTENT_DISPOSITION='attachment; filename="malicious.php"',
    )
    assert r.status_code == 400  # Expecting a bad request
