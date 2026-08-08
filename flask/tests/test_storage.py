from app import core
from app.storage import AzureBlobDocumentStorage, LocalDocumentStorage


class FakeBlob:
    def __init__(self):
        self.content = None

    def upload_blob(self, content, overwrite=False):
        assert overwrite is True
        self.content = content

    def download_blob(self):
        return self

    def readall(self):
        return self.content


class FakeContainer:
    def __init__(self):
        self.blobs = {}

    def get_blob_client(self, name):
        return self.blobs.setdefault(name, FakeBlob())


def test_local_storage_round_trip(tmp_path):
    storage = LocalDocumentStorage(tmp_path)
    storage.save("nested/document.txt", b"content")
    assert storage.read("nested/document.txt") == b"content"


def test_blob_storage_round_trip(monkeypatch):
    monkeypatch.setattr(core, "AZURE_STORAGE_PREFIX", "contracts")
    storage = AzureBlobDocumentStorage(FakeContainer())
    storage.save("document.txt", b"content")
    assert storage.read("document.txt") == b"content"
