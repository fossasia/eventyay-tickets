import hashlib
import os
import urllib.parse
from io import BytesIO, StringIO

import requests
from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files import File
from django.core.files.storage import Storage


"""
This file contains a Django storage backend for the minimal CDN used by the venueless SaaS service. The architecture
of the CDN is described at https://behind.pretix.eu/2018/03/20/high-available-cdn/
"""


class NanoCDNFile(File):
    def __init__(self, name, storage, mode="rb"):
        self.mode = mode
        self.name = name
        self._storage = storage
        self._is_read = False
        self.file = BytesIO()
        self._resp = None

    def write(self, content):
        raise NotImplementedError()

    def _read(self):
        self._resp = self._storage._read(self.name)
        b = self._resp.content
        if "b" not in self.mode:
            self.file = StringIO(b.decode(self._resp.encoding or "utf-8"))
        else:
            self.file = BytesIO(b)
        self._is_read = True
        return b

    @property
    def size(self):
        if not hasattr(self, "_size"):
            if self._is_read:
                self._read()
            if "Content-Length" in self._resp.headers:
                self._size = self._resp.headers["Content-Length"]
            else:
                self._size = len(self.file.getvalue())
        return self._size

    def chunks(self, chunk_size=None):
        if not chunk_size:
            chunk_size = self.DEFAULT_CHUNK_SIZE

        self._resp = self._storage._read(self.name)
        if "Content-Length" in self._resp.headers:
            self._size = self._resp.headers["Content-Length"]

        def it():
            if self._is_read:
                yield self.file.read()
                return
            s = 0
            for chunk in self._resp.iter_content(chunk_size=chunk_size):
                if chunk:
                    yield chunk
                    s += len(chunk)
            if not hasattr(self, "_size"):
                self._size = s

        return it()

    def read(self, num_bytes=None):
        if not self._is_read:
            self._read()
        return self.file.read(num_bytes)


class NanoCDNStorage(Storage):
    def __init__(self):
        self.base_url = settings.NANOCDN_URL

    def _open(self, name, mode="rb"):
        if isinstance(name, NanoCDNFile):
            return name
        return NanoCDNFile(name, self, mode)

    def _read(self, name):
        resp = requests.get(urllib.parse.urljoin(self.base_url, name), stream=True)
        if resp.status_code == 404:
            raise FileNotFoundError()
        resp.raise_for_status()
        return resp

    def _save(self, name, content):
        content = content.read()

        sha1 = hashlib.sha1()
        sha1.update(content.encode() if isinstance(content, str) else content)

        parts = name.split("/")
        if parts[1] in ("pub", "priv"):
            parts = parts[1:]
        elif parts[0] not in ("pub", "priv"):
            parts = ["priv"] + parts
        name = "/".join(parts)

        if "." in os.path.basename(name):
            bname, ext = os.path.basename(name).rsplit(".", 1)
            name = os.path.join(
                os.path.dirname(name), bname + "." + sha1.hexdigest()[:14] + "." + ext
            )
        else:
            name = os.path.join(
                os.path.dirname(name), os.path.basename(name) + "." + sha1[:14]
            )

        resp = requests.put(
            urllib.parse.urljoin(self.base_url, os.path.join("upload", name)),
            data=content,
            allow_redirects=False,
        )
        if resp.status_code != 409:
            resp.raise_for_status()

        loc = resp.headers["Location"]
        if loc.startswith("/"):
            loc = loc[1:]
        return loc

    def get_available_name(self, name, max_length=None):
        if max_length and len(name) + 15 > max_length:
            raise SuspiciousFileOperation(
                'Storage can not find an available filename for "%s". '
                "Please make sure that the corresponding file field "
                'allows sufficient "max_length".' % name
            )
        return name

    def delete(self, name):
        if isinstance(name, NanoCDNFile):
            name = name.name
        resp = requests.delete(urllib.parse.urljoin(self.base_url, name))
        if resp.status_code == 404:
            return resp  # That is fine
        resp.raise_for_status()
        return resp

    def exists(self, name):
        resp = requests.head(urllib.parse.urljoin(self.base_url, name))
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        return True

    def size(self, name):
        resp = requests.head(urllib.parse.urljoin(self.base_url, name))
        resp.raise_for_status()
        return resp["Content-Length"]

    def url(self, name):
        return urllib.parse.urljoin(settings.MEDIA_URL, name)
