import os
import unicodedata

from django.utils.crypto import get_random_string


def path_with_hash(name):
    dir_name, file_name = os.path.split(name)
    file_root, file_ext = os.path.splitext(file_name)
    random = get_random_string(7)
    return os.path.join(dir_name, f"{file_root}_{random}{file_ext}")


def safe_filename(filename):
    return unicodedata.normalize("NFD", filename).encode("ASCII", "ignore").decode()
