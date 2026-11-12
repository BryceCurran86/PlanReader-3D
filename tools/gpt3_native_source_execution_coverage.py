"""Read-only native-input coverage through the existing source authority.

This bridge proves only that every original PDF page was decoded. It grants no
physical existence, semantic/decision completeness, quantity, customer or score
authority. No existing runner or publisher opts into it automatically.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
from stat import S_ISREG
from typing import Any

from pb_migration_contracts import (
    EvidenceResolutionStatus, canonical_contract_json, stable_contract_id,
)
from pb_source_observation_authority import (
    ObservationSelector, SOURCE_OBSERVATION_AUTHORITY_SCHEMA_VERSION,
    SOURCE_OBSERVATION_EXISTS, SourceDecodeCoverageRecord,
    SourceObservationProducer,
)
from tools.gpt3_original_source_preflight import _source_identity_fields, _stable_original_digest


_METHOD = "owner-native-source-execution-coverage"
_VERSION = "1.0.0"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_IDENTITY_FIELDS = _source_identity_fields()


def _original_bytes(path: Path, expected_sha256: str) -> tuple[bytes, tuple[int, ...]]:
    digest, identity = _stable_original_digest(path)
    if digest != expected_sha256:
        raise ValueError("native input coverage original digest mismatch")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if not S_ISREG(metadata.st_mode) or tuple(
            getattr(metadata, name) for name in _IDENTITY_FIELDS
        ) != identity:
            raise ValueError("native input coverage source identity changed")
        # Bound the read to the independently inspected original inode size.
        payload = stream.read(identity[2] + 1)
        completed = os.fstat(stream.fileno())
    after_digest, after_identity = _stable_original_digest(path)
    if (len(payload) != identity[2]
            or hashlib.sha256(payload).hexdigest() != expected_sha256
            or after_digest != expected_sha256 or after_identity != identity
            or tuple(getattr(completed, name) for name in _IDENTITY_FIELDS) != identity):
        raise ValueError("native input coverage source changed during read")
    return payload, identity


def _page_receipt(
    payload: bytes, *, document_id: str, digest: str, page: int, page_count: int,
) -> tuple[str, dict[str, Any]]:
    # The producer and all observation buffers die at this function boundary.
    # A large document never retains one producer/store per decoded page.
    producer = SourceObservationProducer(producer_method=_METHOD, producer_version=_VERSION)
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id, source_bytes=payload,
        source_locator="memory://native-source-execution.pdf", page_ids=(str(page),),
    )
    revision, snapshot = published.revision, published.snapshot
    coverage = producer.authority().coverage(
        document_id=document_id, revision_id=revision.revision_id,
    )
    if (type(coverage) is not SourceDecodeCoverageRecord or coverage != published.coverage
            or coverage.document_id != document_id
            or coverage.revision_id != revision.revision_id
            or type(coverage.total_pages) is not int or coverage.total_pages != page_count
            or coverage.decoded_pages != (page,) or coverage.failed_pages
            or any(type(value) is not int for value in coverage.decoded_pages)
            or coverage.state != ("complete" if page_count == 1 else "partial")
            or revision.document_id != document_id or revision.source_sha256 != digest
            or producer.current_revision_id(document_id) != revision.revision_id
            or snapshot.document_id != document_id or snapshot.source_sha256 != digest
            or snapshot.revision_id != revision.revision_id
            or snapshot.status is not EvidenceResolutionStatus.CORROBORATED
            or snapshot.producer_method != _METHOD or snapshot.producer_version != _VERSION
            or revision.producer_method != _METHOD or revision.producer_version != _VERSION
            or revision.status is not EvidenceResolutionStatus.CORROBORATED
            or not snapshot.observation_ids
            or any(type(value) is not str or not value for value in snapshot.observation_ids)
            or len(set(snapshot.observation_ids)) != len(snapshot.observation_ids)):
        raise ValueError("native input coverage page/revision unavailable or incomplete")
    page_marker = False
    authority = producer.authority()
    for observation_id in snapshot.observation_ids:
        result = authority.resolve(ObservationSelector(
            document_id=document_id, revision_id=revision.revision_id,
            source_sha256=digest, snapshot_id=snapshot.snapshot_id,
            observation_id=observation_id,
        ))
        observation = result.observation
        if (result.status is not EvidenceResolutionStatus.CORROBORATED
                or result.proposition != SOURCE_OBSERVATION_EXISTS
                or observation is None or observation.page_id != str(page)):
            raise ValueError("native input coverage observation lineage unavailable")
        if observation.observation_kind == "native_pdf_page":
            page_marker = True
    if not page_marker:
        raise ValueError("native input coverage page marker unavailable")
    return revision.revision_id, {
        "page_number": page, "snapshot_id": snapshot.snapshot_id,
        "observation_count": len(snapshot.observation_ids),
        "observation_ids_sha256": hashlib.sha256(
            canonical_contract_json(snapshot.observation_ids).encode("utf-8")
        ).hexdigest(),
    }


def build_native_source_execution_coverage(
    *, pdf_path: Path, expected_sha256: str, expected_page_count: int,
) -> dict[str, Any]:
    """Re-ingest every original page; return an input-only JSON-safe receipt."""
    if not isinstance(pdf_path, Path):
        raise TypeError("native input coverage requires a Path")
    if type(expected_sha256) is not str or not _SHA.fullmatch(expected_sha256):
        raise ValueError("native input coverage requires an exact lowercase digest")
    if type(expected_page_count) is not int or expected_page_count < 1:
        raise ValueError("native input coverage requires an original positive page count")
    payload, identity = _original_bytes(pdf_path, expected_sha256)
    document_id = stable_contract_id(
        "source_document", {"source_sha256": expected_sha256}, digest_chars=32,
    )
    pages = []
    revision_id = None
    for page in range(1, expected_page_count + 1):
        current_revision, record = _page_receipt(
            payload, document_id=document_id, digest=expected_sha256,
            page=page, page_count=expected_page_count,
        )
        if revision_id is not None and current_revision != revision_id:
            raise ValueError("native input coverage mixed source revisions")
        revision_id = current_revision
        pages.append(record)
    digest, final_identity = _stable_original_digest(pdf_path)
    if digest != expected_sha256 or final_identity != identity:
        raise ValueError("native input coverage original changed during decode")
    coverage = SourceDecodeCoverageRecord(
        document_id=document_id, revision_id=revision_id, total_pages=expected_page_count,
        decoded_pages=tuple(range(1, expected_page_count + 1)), failed_pages=(), state="complete",
    )
    receipt = {
        "schema_version": SOURCE_OBSERVATION_AUTHORITY_SCHEMA_VERSION,
        "producer_method": _METHOD, "producer_version": _VERSION,
        "source_sha256": expected_sha256, "coverage": asdict(coverage),
        "page_snapshots": pages,
        "semantic_enumeration_complete": None, "decision_scope_complete": None,
        "measurement_authority_granted": False, "commercial_projection_allowed": False,
        "takeoff_eligible": False, "benchmark_score_granted": False,
    }
    receipt["fingerprint"] = hashlib.sha256(
        canonical_contract_json(receipt).encode("utf-8")
    ).hexdigest()
    return json.loads(canonical_contract_json(receipt))


def verify_native_source_execution_coverage(
    receipt: dict[str, Any], *, pdf_path: Path,
    expected_sha256: str, expected_page_count: int,
) -> dict[str, Any]:
    """Independently decode originals again; a public checksum is not proof."""
    if type(receipt) is not dict:
        raise TypeError("native input coverage receipt must be a JSON object")
    actual = build_native_source_execution_coverage(
        pdf_path=pdf_path, expected_sha256=expected_sha256,
        expected_page_count=expected_page_count,
    )
    if canonical_contract_json(receipt) != canonical_contract_json(actual):
        raise ValueError("native input coverage receipt differs from original-page reproof")
    return actual
