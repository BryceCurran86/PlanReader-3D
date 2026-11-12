"""Original source-registered Maryborough ceiling -> trusted RCP callout bridge."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import os
from pathlib import Path

import fitz
import pytest

from pb_source_visibility_authority import SourceVisibilityProducer
from pb_source_rcp_height_material_evidence import (
    bind_original_rcp_height_to_issued_ceiling,
)
from pb_source_cross_view_floor_correspondence_shadow import (
    EvidenceResolutionStatus,
    authenticate_maryborough_office_rcp_ceiling_correspondence,
    authenticate_maryborough_food_prep_rcp_ceiling_correspondence,
    get_authenticated_ceiling_correspondence,
)
from pb_maryborough_ceiling_customer import (
    OFFICE_PHYSICAL_CEILING_ID,
    FOOD_PREP_PHYSICAL_CEILING_ID,
    MARYBOROUGH_DOCUMENT_ID,
    OFFICE_PHYSICAL_ROOM_ID,
    FOOD_PREP_PHYSICAL_ROOM_ID,
    OFFICE_SOURCE_ROOM_FACE_ID,
    FOOD_PREP_SOURCE_ROOM_FACE_ID,
)

SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


@pytest.fixture(scope="module")
def genuine_ceiling_source():
    value = os.environ.get("PLANREADER_ORIGINAL_MARYBOROUGH") or os.environ.get(
        "PLANREADER_MARYBOROUGH_ORIGINAL_PDF"
    )
    if not value:
        pytest.skip("ORIGINAL_SOURCE_NOT_RUN: private original unavailable, not a proof pass")
    path = Path(value)
    assert path.is_file() and not path.is_symlink()
    source_bytes = path.read_bytes()
    assert hashlib.sha256(source_bytes).hexdigest() == SHA
    producer = SourceVisibilityProducer(
        producer_method="gptmax-original-issued-ceiling-height-test",
        producer_version="1",
        source_native_finish_text_shadow=True,
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=MARYBOROUGH_DOCUMENT_ID,
        source_bytes=source_bytes,
        source_locator=str(path),
        page_ids=("9",),
    )
    issued = {}
    with fitz.open(stream=source_bytes, filetype="pdf") as doc:
        for label, function, ceiling_id, room_id, face_id in (
            ("office", authenticate_maryborough_office_rcp_ceiling_correspondence,
             OFFICE_PHYSICAL_CEILING_ID, OFFICE_PHYSICAL_ROOM_ID, OFFICE_SOURCE_ROOM_FACE_ID),
            ("food_prep", authenticate_maryborough_food_prep_rcp_ceiling_correspondence,
             FOOD_PREP_PHYSICAL_CEILING_ID, FOOD_PREP_PHYSICAL_ROOM_ID, FOOD_PREP_SOURCE_ROOM_FACE_ID),
        ):
            rec = function(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=SHA, snapshot_id=published.snapshot.snapshot_id,
                canonical_ceiling_id=ceiling_id, physical_room_id=room_id,
                canonical_room_id=room_id, source_room_face_record_id=face_id,
                doc=doc,
            )
            assert rec.status is EvidenceResolutionStatus.CORROBORATED
            assert rec.commercial_projection_allowed and rec.takeoff_eligible
            assert get_authenticated_ceiling_correspondence(rec.snapshot_id, rec.record_id) is rec
            issued[label] = rec
    return producer, published, issued


def test_genuine_office_and_food_prep_ceiling_height_attached_to_original_issued_zone(genuine_ceiling_source):
    source, published, issued = genuine_ceiling_source
    expected = {"office": (2400, "GRID", 9.05352), "food_prep": (3000, "FPB", 13.270425)}
    observed_ids = set()
    for label, rec in issued.items():
        result = bind_original_rcp_height_to_issued_ceiling(
            source=source, correspondence=rec,
        )
        height, finish, existing_area = expected[label]
        assert (result.status, result.height_mm, result.material_code) == (
            "AUTHENTICATED_EXISTING_CEILING_RCP_HEIGHT_SOURCE", height, finish,
        )
        assert rec.area_m2 == existing_area
        assert result.canonical_ceiling_id == rec.canonical_ceiling_id
        assert result.correspondence_record_id == rec.record_id
        assert result.source_sha256 == SHA
        assert result.source_height_record_id not in observed_ids
        observed_ids.add(result.source_height_record_id)
        assert not result.physical_zone_area_reissued
        assert not result.wall_finish_height_authenticated
        assert not result.commercial_projection_allowed
        assert not result.benchmark_credit
        replay = bind_original_rcp_height_to_issued_ceiling(
            source=source, correspondence=rec,
        )
        assert replay == result


def test_unissued_or_mutated_correspondence_cannot_claim_ceiling_height(genuine_ceiling_source):
    source, _, issued = genuine_ceiling_source
    rec = issued["office"]
    for invalid in (
        replace(rec, ceiling_height_mm=2700.0),
        replace(rec, finish_code="FPB"),
        replace(rec, support_dimension_box_pdf_pts=(0.0, 0.0, 1.0, 1.0)),
        replace(rec, snapshot_id="foreign-snapshot"),
        replace(rec, commercial_projection_allowed=False),
        replace(rec, source_room_face_record_id="foreign-face"),
        object(),
    ):
        result = bind_original_rcp_height_to_issued_ceiling(
            source=source, correspondence=invalid,
        )
        assert result.status == "ABSTAIN"
        assert result.height_mm is None
        assert not result.commercial_projection_allowed
        assert not result.benchmark_credit


def test_original_source_mismatch_or_unavailable_page_fails_closed(genuine_ceiling_source):
    source, published, issued = genuine_ceiling_source
    empty = SourceVisibilityProducer(
        producer_method="gptmax-original-issued-ceiling-unprovisioned",
        producer_version="1",
        source_native_finish_text_shadow=True,
    )
    result = bind_original_rcp_height_to_issued_ceiling(
        source=empty, correspondence=issued["office"],
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == ("original_rcp_ceiling_source_snapshot_mismatch",)
    assert result.height_mm is None
