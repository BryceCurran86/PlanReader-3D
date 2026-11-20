"""Any source PDF can yield review-only cross-sheet geometric candidates."""
import hashlib

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_cross_view_floor_correspondence_shadow import (
    SourceCrossViewFloorCorrespondenceProducer,
    SourceCrossViewFloorCorrespondenceSelector,
)


def _original():
    pdf = fitz.open()
    p1 = pdf.new_page(width=220, height=220)
    for row in (30, 170):
        p1.draw_line((30, row), (170, row), color=(0, 0, 0), width=2)
    for x in (30, 170):
        p1.draw_line((x, 30), (x, 170), color=(0, 0, 0), width=2)
    p1.insert_text((65, 80), "FX42", fontsize=14)
    p1.insert_text((180, 180), "FX91", fontsize=9)
    p1.draw_line((40, 40), (125, 125), color=(0, .5, 0), width=3)
    p2 = pdf.new_page(width=220, height=220)
    for row in (30, 170):
        p2.draw_line((30, row), (170, row), color=(0, 0, 0), width=2)
    for x in (30, 170):
        p2.draw_line((x, 30), (x, 170), color=(0, 0, 0), width=2)
    data = pdf.tobytes()
    pdf.close()
    return data


def _selector(data, **options):
    base = dict(
        document_id="unknown-project-3000", revision_id="original-1",
        source_sha256=hashlib.sha256(data).hexdigest(), snapshot_id="snap-1",
        support_page_id="1", target_page_id="2", material_code="FX42",
    )
    base.update(options)
    return SourceCrossViewFloorCorrespondenceSelector(**base)


def _boxes():
    return [{
        "dimension_box_pdf_pts": (30., 30., 170., 170.),
        "canonical_floor_id": "physical-floor-a",
        "physical_room_id": "physical-room-a",
        "source_room_face_record_id": "W4-real-room-a",
    }]


def test_unknown_pdf_native_source_segments_and_all_finish_competitors(monkeypatch):
    data = _original()
    seen = {}
    def collect(_self, **kwargs):
        seen.update(kwargs)
        return "geometric_candidate_only"
    monkeypatch.setattr(SourceCrossViewFloorCorrespondenceProducer,
                        "evaluate_synthetic", collect)
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_source_native(
        selector=_selector(data), original_pdf_bytes=data,
        measured_boxes=_boxes(), finish_codes=("FX42", "FX91"),
        trials=4,
    )
    assert result == "geometric_candidate_only"
    assert seen["selector"].material_code == "FX42"
    assert {m["code"] for m in seen["marks"]} == {"FX42", "FX91"}
    assert next(m for m in seen["marks"] if m["code"] == "FX42")["registered_region"] is True
    assert next(m for m in seen["marks"] if m["code"] == "FX91")["registered_region"] is False
    assert len(seen["support_segments"]) >= 4
    assert len(seen["target_segments"]) >= 4
    assert seen["trials"] == 4


def test_invalid_pdf_digest_or_page_never_produces_a_registered_receipt():
    data = _original()
    producer = SourceCrossViewFloorCorrespondenceProducer()
    for selector in (
        _selector(data, source_sha256="f" * 64),
        _selector(data, support_page_id="5"),
        _selector(data, target_page_id="1"),
    ):
        result = producer.evaluate_source_native(
            selector=selector, original_pdf_bytes=data,
            measured_boxes=_boxes(), finish_codes=("FX42", "FX91"),
        )
        assert result.status is EvidenceResolutionStatus.ABSTAINED
        assert result.records == ()


@pytest.mark.parametrize("finish_codes", [
    ("UNRELATED",), ("fx42",), ("FX42 ",),
    ("FX42", "BAD!"), (), ("FX42",) * 201,
])
def test_source_finish_codes_must_be_explicit_and_well_formed(finish_codes):
    data = _original()
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_source_native(
        selector=_selector(data), original_pdf_bytes=data,
        measured_boxes=_boxes(), finish_codes=finish_codes,
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.records == ()


def test_valid_geometric_match_remains_noncommercial_source_candidate():
    data = _original()
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_source_native(
        selector=_selector(data), original_pdf_bytes=data,
        measured_boxes=_boxes(), finish_codes=("FX42", "FX91"), trials=2,
    )
    assert result.status in {
        EvidenceResolutionStatus.CANDIDATE, EvidenceResolutionStatus.ABSTAINED,
        EvidenceResolutionStatus.CONFLICT,
    }
    assert all(not r.commercial_projection_allowed and not r.takeoff_eligible
               for r in result.records)
