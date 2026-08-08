"""Document byte storage with local development and Azure Blob backends."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from . import core


class DocumentStorage(Protocol):
    def save(self, name: str, content: bytes) -> None: ...

    def read(self, name: str) -> bytes: ...


def _validate_name(name: str) -> str:
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("storage names must be relative and traversal-free")
    return path.as_posix()


class LocalDocumentStorage:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, name: str, content: bytes) -> None:
        target = self.root / _validate_name(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    def read(self, name: str) -> bytes:
        return (self.root / _validate_name(name)).read_bytes()


class AzureBlobDocumentStorage:
    def __init__(self, container):
        self.container = container

    def _blob_name(self, name: str) -> str:
        safe_name = _validate_name(name)
        prefix = core.AZURE_STORAGE_PREFIX.strip("/")
        return f"{prefix}/{safe_name}" if prefix else safe_name

    def save(self, name: str, content: bytes) -> None:
        self.container.get_blob_client(self._blob_name(name)).upload_blob(content, overwrite=True)

    def read(self, name: str) -> bytes:
        return self.container.get_blob_client(self._blob_name(name)).download_blob().readall()


def build_document_storage() -> DocumentStorage:
    if not (core.AZURE_STORAGE_CONNECTION_STRING or core.AZURE_STORAGE_ACCOUNT_URL):
        return LocalDocumentStorage(core.DOCUMENT_STORAGE)

    try:
        from azure.storage.blob import BlobServiceClient
    except ImportError as exc:  # pragma: no cover - only reached in a misconfigured deployment
        raise RuntimeError("Azure Blob storage is configured but azure-storage-blob is not installed") from exc

    if core.AZURE_STORAGE_CONNECTION_STRING:
        service = BlobServiceClient.from_connection_string(core.AZURE_STORAGE_CONNECTION_STRING)
    else:
        try:
            from azure.identity import DefaultAzureCredential
        except ImportError as exc:  # pragma: no cover - only reached in a misconfigured deployment
            raise RuntimeError("Managed-identity Blob storage requires azure-identity") from exc
        service = BlobServiceClient(core.AZURE_STORAGE_ACCOUNT_URL, credential=DefaultAzureCredential())
    return AzureBlobDocumentStorage(service.get_container_client(core.AZURE_STORAGE_CONTAINER))


document_storage = build_document_storage()
