"""Live source-owned ceiling-lining extractor integration tests."""
from __future__ import annotations

import fitz

import pb_live_ceiling_lining_integration as live_module
from pb_page_scale_calibration_authority import POINTS_PER_METRE_AT_1_1
from pb_ceiling_lining_review_promotion import (
    collect_ceiling_lining_review_candidates,
)
from pb_live_ceiling_lining_integration import (
    LIVE_CEILING_LINING_RESOLVED,
    LIVE_CEILING_LINING_TAG_FAMILY_CONFLICT,
    collect_live_ceiling_lining_claims,
)
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def _pdf_bytes(*, framed: bool = True) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=460.0, height=320.0)

        if framed:
            page.draw_rect(
                fitz.Rect(30.0, 25.0, 370.0, 230.0),
                color=(0, 0, 0),
                width=1.0,
            )
            page.insert_text(
                fitz.Point(120.0, 48.0),
                "GROUND FLOOR PLAN",
                fontsize=8.0,
                color=(0, 0, 0),
            )

        # Two rooms sharing a physical wall, wholly inside the viewport.
        for first, second in (
            ((70.0, 70.0), (330.0, 70.0)),
            ((330.0, 70.0), (330.0, 175.0)),
            ((330.0, 175.0), (70.0, 175.0)),
            ((70.0, 175.0), (70.0, 70.0)),
            ((200.0, 70.0), (200.0, 175.0)),
        ):
            page.draw_line(
                fitz.Point(*first),
                fitz.Point(*second),
                color=(0, 0, 0),
                width=1.0,
            )

        page.insert_text(
            fitz.Point(92.0, 122.0),
            "CEILING FINISH: CHIPBOARD",
            fontsize=7.0,
            color=(0, 0, 0),
        )

        span = POINTS_PER_METRE_AT_1_1 / 100.0
        x0, x1, y = 95.0, 95.0 + span, 205.0
        shape = page.new_shape()
        shape.draw_line(fitz.Point(x0, y), fitz.Point(x1, y))
        shape.draw_line(fitz.Point(x0, y - 6.0), fitz.Point(x0, y + 6.0))
        shape.draw_line(fitz.Point(x1, y - 6.0), fitz.Point(x1, y + 6.0))
        shape.finish(width=1.0)
        shape.commit()
        page.insert_text(fitz.Point(x0 - 2.0, y + 18.0), "0", fontsize=7.0)
        page.insert_text(fitz.Point(x1 - 4.0, y + 18.0), "1m", fontsize=7.0)

        # Keep generic extractor drawing-page classification positive.
        page.insert_text(
            fitz.Point(390.0, 285.0),
            "SCALE 1:100",
            fontsize=7.0,
        )
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _write(tmp_path, *, framed: bool = True):
    path = tmp_path / ("framed.pdf" if framed else "unframed.pdf")
    path.write_bytes(_pdf_bytes(framed=framed))
    return path


def test_resolved_floor_plan_emits_live_chipboard_ceiling_claim(tmp_path) -> None:
    path = _write(tmp_path, framed=True)

    result = collect_live_ceiling_lining_claims(path, pages=(0,))

    assert result.reason_codes[0] == LIVE_CEILING_LINING_RESOLVED
    assert len(result.claims) == 1
    claim = result.claims[0]
    assert claim.tag == "ceiling_chipboard"
    assert claim.finish_descriptor == "chipboard"
    assert claim.quantity_m2 > 0.0
    assert claim.status == "provisional"
    assert claim.room_quantity_ids
    assert claim.room_entity_ids
    assert claim.evidence_ids
    assert claim.physical_scale_record_id
    assert len(result.quantity_evidence) == 1
    assert result.quantity_evidence[0].quantity_id in claim.room_quantity_ids
    assert len(result.canonical_ceilings) == 1
    ceiling = result.canonical_ceilings[0]
    assert ceiling.document_id
    assert ceiling.snapshot_id
    assert ceiling.source_sha256
    assert ceiling.revision_id
    assert ceiling.room_entity_id in claim.room_entity_ids
    assert ceiling.area_m2 == claim.quantity_m2
    assert ceiling.finish_descriptor == claim.finish_descriptor
    assert ceiling.polygon_pdf_pts
    assert ceiling.geometry_complete is True
    assert ceiling.metric_area_complete is True
    assert ceiling.metric_geometry_complete is False


def test_runtime_collector_returns_only_review_gated_ceiling_candidate(tmp_path) -> None:
    path = _write(tmp_path, framed=True)

    candidates = collect_ceiling_lining_review_candidates(
        path,
        pages=(0,),
        workspace_id=17,
        project_id="project-ceiling-runtime",
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    row = dict(candidate.review_row)
    assert row["workspace_id"] == 17
    assert row["project_id"] == "project-ceiling-runtime"
    assert row["origin"] == "AI"
    assert row["quantity_status"] == "To review"
    assert row["row_role"] == "ceiling_area"
    assert row["quantity"] > 0.0
    assert candidate.promoted_quantity.metadata["shadow_only"] is False
    assert (
        candidate.promoted_quantity.metadata["commercial_projection_allowed"]
        is True
    )


def test_generic_extractor_publishes_only_separate_live_provisional_prediction(tmp_path) -> None:
    path = _write(tmp_path, framed=True)

    extractor = GenericPlanReaderExtractor()
    predictions = extractor.extract_from_pdf(
        path,
        pages=(0,),
        collect_item35_shadow=False,
    )

    ceiling = [item for item in predictions if item.tag == "ceiling_chipboard"]
    assert len(ceiling) == 1
    prediction = ceiling[0]
    assert prediction.quantity is not None and prediction.quantity > 0.0
    assert prediction.trade_type == "finishes"
    assert prediction.unit == "SM"
    assert prediction.metadata["derivation"] == "source_owned_ceiling_lining"
    assert prediction.metadata["live_authority_status"] == "provisional"
    assert prediction.metadata["commercial_projection_allowed"] is False
    assert prediction.metadata["physical_scale_record_id"]
    assert prediction.metadata["canonical_ceiling_ids"]
    assert prediction.metadata["canonical_ceiling_objects"]
    assert extractor.ceiling_lining_live["status"] == "corroborated"
    assert extractor.canonical_ceilings_live["status"] == "corroborated"
    assert len(extractor.canonical_ceilings_live["ceilings"]) == 1


def test_unframed_plan_does_not_fall_back_to_page_wide_ceiling_authority(tmp_path) -> None:
    path = _write(tmp_path, framed=False)

    extractor = GenericPlanReaderExtractor()
    predictions = extractor.extract_from_pdf(
        path,
        pages=(0,),
        collect_item35_shadow=False,
    )

    assert not any(item.tag.startswith("ceiling_") for item in predictions)
    assert extractor.ceiling_lining_live["claims"] == []
    assert extractor.canonical_ceilings_live["ceilings"] == []


def _pdf_with_two_board_descriptors() -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=460.0, height=320.0)
        page.draw_rect(
            fitz.Rect(30.0, 25.0, 370.0, 230.0),
            color=(0, 0, 0),
            width=1.0,
        )
        page.insert_text(
            fitz.Point(120.0, 48.0),
            "GROUND FLOOR PLAN",
            fontsize=8.0,
            color=(0, 0, 0),
        )
        for first, second in (
            ((70.0, 70.0), (330.0, 70.0)),
            ((330.0, 70.0), (330.0, 175.0)),
            ((330.0, 175.0), (70.0, 175.0)),
            ((70.0, 175.0), (70.0, 70.0)),
            ((200.0, 70.0), (200.0, 175.0)),
        ):
            page.draw_line(
                fitz.Point(*first),
                fitz.Point(*second),
                color=(0, 0, 0),
                width=1.0,
            )
        page.insert_text(
            fitz.Point(86.0, 115.0),
            "CEILING FINISH: BOARD TYPE A",
            fontsize=6.5,
        )
        page.insert_text(
            fitz.Point(218.0, 115.0),
            "CEILING FINISH: BOARD TYPE B",
            fontsize=6.5,
        )
        span = POINTS_PER_METRE_AT_1_1 / 100.0
        x0, x1, y = 95.0, 95.0 + span, 205.0
        shape = page.new_shape()
        shape.draw_line(fitz.Point(x0, y), fitz.Point(x1, y))
        shape.draw_line(fitz.Point(x0, y - 6.0), fitz.Point(x0, y + 6.0))
        shape.draw_line(fitz.Point(x1, y - 6.0), fitz.Point(x1, y + 6.0))
        shape.finish(width=1.0)
        shape.commit()
        page.insert_text(fitz.Point(x0 - 2.0, y + 18.0), "0", fontsize=7.0)
        page.insert_text(fitz.Point(x1 - 4.0, y + 18.0), "1m", fontsize=7.0)
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def test_distinct_finish_descriptors_that_share_one_family_tag_abstain(tmp_path) -> None:
    path = tmp_path / "tag-conflict.pdf"
    path.write_bytes(_pdf_with_two_board_descriptors())

    result = collect_live_ceiling_lining_claims(path, pages=(0,))

    assert result.claims == ()
    assert result.quantity_evidence == ()
    assert LIVE_CEILING_LINING_TAG_FAMILY_CONFLICT in result.reason_codes
    assert len(result.canonical_ceilings) == 2
    assert len(
        {ceiling.canonical_ceiling_id for ceiling in result.canonical_ceilings}
    ) == 2
    assert {
        ceiling.finish_descriptor for ceiling in result.canonical_ceilings
    } == {"board type a", "board type b"}

def _documented_area_claim_fixture(*, include_figured_ids: bool = True):
    from types import SimpleNamespace

    from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
    from pb_migration_contracts import QuantityEvidence
    import pb_live_ceiling_lining_integration as live

    scope = "source-room-face:1"
    area = QuantityEvidence(
        quantity_id="qty-room-area-documented",
        family="room_area",
        semantic_key=f"room_area:{scope}",
        value=13.270425,
        unit="m2",
        input_entity_ids=(scope,),
        formula="authoritative_explicit_area",
        formula_version="test",
        evidence_ids=("ev-dim-h", "ev-dim-v"),
        authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        status=AuthorityStatus.FIRM.value,
        confidence=1.0,
        abstained=False,
        blocking_reasons=(),
        metadata={
            "source_sha256": "a" * 64,
            "revision_id": "rev-1",
            "page_no": 1,
            "viewport_id": "vp-1",
            "figured_dimension_ids": (
                ["dim-h", "dim-v"] if include_figured_ids else []
            ),
        },
    )
    ceiling = QuantityEvidence(
        quantity_id="qty-ceiling",
        family="ceiling_lining",
        semantic_key=f"ceiling_lining:{scope}",
        value=13.270425,
        unit="m2",
        input_entity_ids=(scope,),
        formula="reuse_same_scope_authoritative_area_with_explicit_ceiling_finish",
        formula_version="test",
        evidence_ids=("ev-dim-h", "ev-dim-v", "ev-finish"),
        authority=MeasurementAuthorityType.MODEL_DERIVED.value,
        status=AuthorityStatus.PROVISIONAL.value,
        confidence=1.0,
        abstained=False,
        blocking_reasons=(),
        metadata={
            "shadow_only": True,
            "commercial_projection_allowed": False,
            "viewport_id": "vp-1",
            "page_no": 1,
            "finish_descriptor": "plasterboard",
            "finish_source_methods": (live.SOURCE_CEILING_FINISH_METHOD,),
            "finish_evidence_ids": ("ev-finish",),
            "upstream_area_quantity_id": area.quantity_id,
        },
    )
    source_result = SimpleNamespace(
        room_area_quantities=(area,),
        scale_bridge=SimpleNamespace(
            status=None,
            calibration=None,
            physical_scale_evidence=None,
        ),
    )
    return live, ceiling, source_result


def test_live_ceiling_accepts_documented_dimension_area_without_scale() -> None:
    from pb_geometry_takeoff_model import MeasurementAuthorityType

    live, ceiling, source_result = _documented_area_claim_fixture()
    resolved = live._claim_from_quantity(
        quantity=ceiling,
        source_result=source_result,
        page_no=1,
        viewport_id="vp-1",
    )
    assert resolved is not None
    assert resolved[2] == 13.270425
    assert resolved[6] == ""
    assert resolved[7] == MeasurementAuthorityType.DOCUMENTED_DIMENSION.value
    assert resolved[8] == ("dim-h", "dim-v")


def test_live_ceiling_documented_dimension_requires_figured_lineage() -> None:
    live, ceiling, source_result = _documented_area_claim_fixture(
        include_figured_ids=False
    )
    assert (
        live._claim_from_quantity(
            quantity=ceiling,
            source_result=source_result,
            page_no=1,
            viewport_id="vp-1",
        )
        is None
    )



def test_ceiling_evidence_pages_are_ingested_but_only_topology_pages_are_scanned(
    tmp_path,
    monkeypatch,
) -> None:
    doc = fitz.open()
    try:
        doc.new_page(width=300.0, height=200.0)
        doc.new_page(width=300.0, height=200.0)
        path = tmp_path / "evidence-topology-split.pdf"
        path.write_bytes(doc.tobytes())
    finally:
        doc.close()

    ingested_page_ids = []
    original_ingest = live_module.SourceVisibilityProducer.ingest_native_pdf_bytes

    def _capture_ingest(self, *args, **kwargs):
        ingested_page_ids.extend(kwargs.get("page_ids") or ())
        return original_ingest(self, *args, **kwargs)

    scanned_page_numbers = []

    def _capture_floor_plans(page, *, page_number):
        scanned_page_numbers.append(page_number)
        return ()

    monkeypatch.setattr(
        live_module.SourceVisibilityProducer,
        "ingest_native_pdf_bytes",
        _capture_ingest,
    )
    monkeypatch.setattr(
        live_module,
        "authoritative_floor_plan_viewports",
        _capture_floor_plans,
    )

    result = collect_live_ceiling_lining_claims(
        path,
        pages=(0, 1),
        topology_pages=(0,),
    )

    assert ingested_page_ids == ["1", "2"]
    assert scanned_page_numbers == [1]
    assert result.claims == ()


def test_ceiling_topology_pages_must_be_subset_of_evidence_pages(tmp_path) -> None:
    import pytest

    doc = fitz.open()
    try:
        doc.new_page(width=300.0, height=200.0)
        doc.new_page(width=300.0, height=200.0)
        path = tmp_path / "invalid-evidence-topology-split.pdf"
        path.write_bytes(doc.tobytes())
    finally:
        doc.close()

    with pytest.raises(ValueError, match="topology_pages must be a subset of pages"):
        collect_live_ceiling_lining_claims(
            path,
            pages=(0,),
            topology_pages=(1,),
        )
