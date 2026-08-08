"""Behavioral contract checks shared by the Django, FastAPI, and Flask APIs.

Each framework supplies a small adapter around its in-process test client. The
assertions intentionally only use the public HTTP shape, so the same checks
also describe what a deployed HTTP contract test must exercise.
"""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from typing import Any, Protocol


MAX_DOCUMENT_BYTES = 15 * 1024 * 1024


@dataclass
class ContractResponse:
    status_code: int
    body: Any


class ContractAdapter(Protocol):
    def health(self) -> ContractResponse: ...

    def upload(self, archive: bytes, variables: list[str], filename: str = "contracts.zip") -> ContractResponse: ...

    def get_batch(self, batch_id: str) -> ContractResponse: ...

    def get_document(self, document_id: str) -> ContractResponse: ...

    def review(self, finding_id: str, decision: str, reviewer_name: str) -> ContractResponse: ...

    def drain_queue(self) -> None: ...


def make_archive(*files: tuple[str, bytes], compression: int = zipfile.ZIP_STORED) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=compression) as archive:
        for name, content in files:
            archive.writestr(name, content)
    return output.getvalue()


def _assert_common_fields(body: dict[str, Any], fields: set[str]) -> None:
    assert fields <= body.keys(), f"missing fields: {fields - body.keys()}"


def _assert_document(document: dict[str, Any]) -> None:
    _assert_common_fields(
        document,
        {"id", "original_filename", "size_bytes", "status", "error_message", "created_at", "processed_at", "findings"},
    )
    assert isinstance(document["id"], str)
    assert isinstance(document["findings"], list)


def run_contract_suite(adapter: ContractAdapter) -> None:
    """Run the public workflow and the core ZIP boundary checks for one API."""

    response = adapter.health()
    assert response.status_code == 200
    assert response.body == {"status": "ok"}

    response = adapter.upload(
        make_archive(("nested/agreement.txt", b"contract text")),
        ["effective_date", "monthly_rent"],
    )
    assert response.status_code == 202
    batch = response.body
    _assert_common_fields(batch, {"id", "variables", "submitted_by_subject", "status", "created_at", "completed_at", "documents"})
    assert batch["variables"] == ["effective_date", "monthly_rent"]
    assert len(batch["documents"]) == 1
    _assert_document(batch["documents"][0])
    document_id = batch["documents"][0]["id"]

    adapter.drain_queue()
    response = adapter.get_batch(batch["id"])
    assert response.status_code == 200
    batch = response.body
    assert batch["status"] == "completed"
    assert len(batch["documents"]) == 1
    document = batch["documents"][0]
    assert document["id"] == document_id
    assert document["status"] == "completed"
    assert len(document["findings"]) == 2
    finding = document["findings"][0]
    _assert_common_fields(
        finding,
        {"id", "variable_name", "extracted_value", "review_status", "reviewer_name", "reviewer_subject", "reviewed_at", "created_at"},
    )
    assert finding["review_status"] == "pending"

    response = adapter.get_document(document_id)
    assert response.status_code == 200
    assert response.body["id"] == document_id
    assert response.body["status"] == "completed"

    response = adapter.review(finding["id"], "accepted", "Asha")
    assert response.status_code == 200
    assert response.body["review_status"] == "accepted"
    assert response.body["reviewer_name"] == "Asha"

    duplicate_variables = adapter.upload(
        make_archive(("duplicate.txt", b"text")),
        ["effective_date", " effective_date "],
    )
    assert duplicate_variables.status_code == 422
    invalid_review = adapter.review(finding["id"], "accepted", "")
    assert invalid_review.status_code == 422

    malformed = adapter.upload(b"not a ZIP archive", ["effective_date"])
    assert malformed.status_code == 400

    windows_path = adapter.upload(
        make_archive((r"..\\secret.txt", b"not safe")),
        ["effective_date"],
        filename="windows-path.zip",
    )
    assert windows_path.status_code == 400

    exact_boundary = adapter.upload(
        make_archive(("exact-limit.txt", b"x" * MAX_DOCUMENT_BYTES)),
        ["effective_date"],
        filename="exact-limit.zip",
    )
    assert exact_boundary.status_code == 202
    adapter.drain_queue()
