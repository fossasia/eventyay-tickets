import os
import unicodedata
from pathlib import Path

from django.conf import settings
from django.utils.crypto import get_random_string


def path_with_hash(name, base_path=None, max_length=100):
    base_path = base_path or ""
    dir_name, file_name = os.path.split(name)
    file_root, file_ext = os.path.splitext(file_name)
    file_root = safe_filename(file_root)
    random = get_random_string(7)
    if base_path and max_length:
        # We need to resolve the base path for its actual total length, as absolute
        # paths are stored in the database.
        full_base_path = Path(settings.MEDIA_ROOT) / base_path
        total_length = len(
            str(full_base_path / dir_name / f"{file_root}_{random}{file_ext}")
        )
        if total_length > max_length:
            # If the total length of the path exceeds the max length, we need to
            # shorten the file name by the difference.
            file_root = file_root[: -(total_length - max_length)]
    return str(Path(base_path) / dir_name / f"{file_root}_{random}{file_ext}")


def safe_filename(filename):
    return unicodedata.normalize("NFD", filename).encode("ASCII", "ignore").decode()
