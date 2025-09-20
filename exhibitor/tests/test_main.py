import pytest

from django.core.files.uploadedfile import SimpleUploadedFile

from exhibitors.models import ExhibitorInfo


@pytest.mark.django_db
def test_create_exhibitor_info(event):
    # CREATE: Simulate an image upload and create an exhibitor
    logo = SimpleUploadedFile("test_logo.jpg", b"file_content", content_type="image/jpeg")
    
    exhibitor = ExhibitorInfo.objects.create(
        event=event,
        name="Test Exhibitor",
        description="This is a test exhibitor",
        url="http://testexhibitor.com",
        email="test@example.com",
        logo=logo,
        lead_scanning_enabled=True
    )

    # Verify the exhibitor was created and the fields are correct
    assert exhibitor.name == "Test Exhibitor"
    assert exhibitor.description == "This is a test exhibitor"
    assert exhibitor.url == "http://testexhibitor.com"
    assert exhibitor.email == "test@example.com"
    assert exhibitor.logo.name == "exhibitors/logos/Test Exhibitor/test_logo.jpg"
    assert exhibitor.lead_scanning_enabled is True

@pytest.mark.django_db
def test_read_exhibitor_info(event):
    # CREATE an exhibitor first to test reading
    logo = SimpleUploadedFile("test_logo.jpg", b"file_content", content_type="image/jpeg")
    exhibitor = ExhibitorInfo.objects.create(
        event=event,
        name="Test Exhibitor",
        description="This is a test exhibitor",
        url="http://testexhibitor.com",
        email="test@example.com",
        logo=logo,
        lead_scanning_enabled=True
    )

    # READ: Fetch the exhibitor from the database and verify fields
    exhibitor_from_db = ExhibitorInfo.objects.get(id=exhibitor.id)
    assert exhibitor_from_db.name == "Test Exhibitor"
    assert exhibitor_from_db.description == "This is a test exhibitor"
    assert exhibitor_from_db.url == "http://testexhibitor.com"
    assert exhibitor_from_db.email == "test@example.com"
    assert exhibitor_from_db.lead_scanning_enabled is True

@pytest.mark.django_db
def test_update_exhibitor_info(event):
    # CREATE an exhibitor first to test updating
    logo = SimpleUploadedFile("test_logo.jpg", b"file_content", content_type="image/jpeg")
    exhibitor = ExhibitorInfo.objects.create(
        event=event,
        name="Test Exhibitor",
        description="This is a test exhibitor",
        url="http://testexhibitor.com",
        email="test@example.com",
        logo=logo,
        lead_scanning_enabled=True
    )

    # UPDATE: Modify some fields and save the changes
    exhibitor.name = "Updated Exhibitor"
    exhibitor.description = "This is an updated description"
    exhibitor.lead_scanning_enabled = False
    exhibitor.save()

    # Verify the updated fields
    updated_exhibitor = ExhibitorInfo.objects.get(id=exhibitor.id)
    assert updated_exhibitor.name == "Updated Exhibitor"
    assert updated_exhibitor.description == "This is an updated description"
    assert updated_exhibitor.lead_scanning_enabled is False

@pytest.mark.django_db
def test_delete_exhibitor_info(event):
    # CREATE an exhibitor first to test deleting
    logo = SimpleUploadedFile("test_logo.jpg", b"file_content", content_type="image/jpeg")
    exhibitor = ExhibitorInfo.objects.create(
        event=event,
        name="Test Exhibitor",
        description="This is a test exhibitor",
        url="http://testexhibitor.com",
        email="test@example.com",
        logo=logo,
        lead_scanning_enabled=True
    )

    # DELETE: Delete the exhibitor and verify it no longer exists
    exhibitor_id = exhibitor.id
    exhibitor.delete()

    with pytest.raises(ExhibitorInfo.DoesNotExist):
        ExhibitorInfo.objects.get(id=exhibitor_id)
