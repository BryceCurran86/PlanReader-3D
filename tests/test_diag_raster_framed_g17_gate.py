from __future__ import annotations

import json

import cv2
import fitz
import numpy as np
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _png(gray: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", gray)
    assert ok
    return bytes(encoded)


def _source_pdf() -> bytes:
    gray = np.full((360, 640), 255, np.uint8)
    cv2.rectangle(gray, (30, 150), (240, 164), 0, -1)
    cv2.rectangle(gray, (400, 150), (610, 164), 0, -1)
    cv2.line(gray, (240, 154), (400, 154), 0, 1)
    cv2.line(gray, (240, 160), (400, 160), 0, 1)

    doc = fitz.open()
    page = doc.new_page(width=320.0, height=180.0)
    page.insert_image(page.rect, stream=_png(gray), keep_proportion=False)
    payload = bytes(doc.tobytes(garbage=4, deflate=True))
    doc.close()
    return payload


def test_diag_raster_framed_g17_gate() -> None:
    producer = SourceVisibilityProducer(
        producer_method="raster-framed-g17-gate-diagnostic",
        producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="raster-framed-g17-gate-diagnostic",
        source_bytes=_source_pdf(),
        source_locator="memory://raster-framed-g17-gate-diagnostic.pdf",
        page_ids=("1",),
    )
    published = producer.augment_with_raster_opening_primitives(
        published.revision.revision_id,
        page_ids=("1",),
    )
    visibility = producer.authority()
    opening = producer.physical_opening_authority()

    primitive_ids = tuple(published.raster_opening_primitive_observation_ids)
    assert primitive_ids

    first_result = None
    first_selector = None
    resolved_records = []
    resolution_failures = []
    kind_counts: dict[str, int] = {}

    for observation_id in primitive_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = visibility.resolve_raster_opening_primitive(selector)
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.observation is not None
        ):
            resolved_records.append(result.observation)
            kind = str(result.observation.observation_kind)
            kind_counts[kind] = kind_counts.get(kind, 0) + 1
            if first_result is None:
                first_result = result
                first_selector = selector
        else:
            resolution_failures.append(
                {
                    "id": observation_id,
                    "status": result.status.value,
                    "reasons": list(result.reason_codes),
                }
            )

    assert first_result is not None
    assert first_selector is not None
    seed = first_result.observation
    assert seed is not None

    snapshot_records, snapshot_failures = opening._raster_primitive_snapshot_records(
        first_result
    )
    raw = opening._raster_framed_candidates_for(seed, snapshot_records)
    scoped = opening._viewport_scoped_raster_candidates_for(
        seed,
        snapshot_records,
        raw,
    )

    final_records = {}
    final_status_counts: dict[str, int] = {}
    final_reason_counts: dict[str, int] = {}
    for observation_id in primitive_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = opening.prove_existence(selector)
        final_status_counts[result.status.value] = (
            final_status_counts.get(result.status.value, 0) + 1
        )
        for reason in result.reason_codes:
            final_reason_counts[str(reason)] = final_reason_counts.get(str(reason), 0) + 1
        if result.existence_record is not None:
            final_records[result.existence_record.record_id] = result.existence_record

    viewport_payload = {}
    if raw:
        from pb_physical_opening_viewport_scope_authority import (
            classify_opening_candidate_viewport_scopes,
        )

        scope = classify_opening_candidate_viewport_scopes(
            source_visibility_producer=producer,
            revision_id=seed.revision_id,
            page_id=seed.page_id,
            snapshot_id=seed.snapshot_id,
            candidates=raw,
            records=snapshot_records,
        )
        viewport_payload = {
            "status": scope.status.value,
            "reason_codes": list(scope.reason_codes),
            "authenticated_viewports": [
                {
                    "view_id": item.view_id,
                    "view_type": item.view_type,
                    "status": item.status,
                    "boundary_source": item.boundary_source,
                    "bbox": list(item.bounding_box),
                }
                for item in scope.authenticated_viewports
            ],
            "decisions": {
                key: {
                    "scope": value.scope,
                    "viewport_id": value.viewport_id,
                    "promotable": value.promotable,
                    "reasons": list(value.reason_codes),
                }
                for key, value in scope.decisions.items()
            },
        }

    payload = {
        "primitive_id_count": len(primitive_ids),
        "direct_resolved_count": len(resolved_records),
        "direct_resolution_failures": resolution_failures[:10],
        "kind_counts": kind_counts,
        "snapshot_record_count": len(snapshot_records),
        "snapshot_failure_count": len(snapshot_failures),
        "snapshot_failure_reasons": [
            list(result.reason_codes) for result in snapshot_failures[:10]
        ],
        "raw_candidate_count": len(raw),
        "raw_candidates": [
            {
                "candidate_id": item.candidate_id,
                "support_count": len(item.source_observation_ids),
                "viewport_id": item.viewport_id,
            }
            for item in raw
        ],
        "scoped_candidate_count": len(scoped),
        "scoped_candidates": [
            {
                "candidate_id": item.candidate_id,
                "support_count": len(item.source_observation_ids),
                "viewport_id": item.viewport_id,
            }
            for item in scoped
        ],
        "viewport": viewport_payload,
        "final_record_count": len(final_records),
        "final_status_counts": final_status_counts,
        "final_reason_counts": final_reason_counts,
    }

    pytest.fail("RASTER_G17_GATE_DIAGNOSTIC=" + json.dumps(payload, sort_keys=True))
