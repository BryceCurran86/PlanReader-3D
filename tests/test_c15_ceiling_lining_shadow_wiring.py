"""C15 ceiling-lining shadow wiring: gold-free adapter tests.

No benchmark IDs, expected BOQ values, project names, or scorer tolerances.
Proves the adapter feeds finalized authoritative area + explicit finish evidence
into build_ceiling_lining_quantity without live/commercial mutation.
"""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pb_ceiling_lining_shadow_adapter import (
    collect_explicit_ceiling_finish_atoms,
    empty_ceiling_lining_shadow,
    resolve_ceiling_lining_shadow,
    shadow_quantity_records,
)
from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_migration_contracts import (
    DocumentEvidence,
    EvidenceAtom,
    EvidenceResolutionStatus,
    QuantityEvidence,
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_migration_provider_envelope import ProviderContext
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor
from pb_quantity_takeoff_adapter import (
    MissingCommercialAuthorityError,
    quantity_evidence_to_takeoff_output_row,
)


SOURCE_SHA = "b" * 64
DOC_ID = "doc-c15-wire"
PAGE_ID = "page-1"
VIEWPORT_ID = "vp-floor-1"
SCOPE_ID = "room-1"
REVISION_ID = "rev-1"


def _context(**overrides) -> ProviderContext:
    values = {
        "run_id": "run-c15-wire",
        "workspace_id": "workspace-c15-wire",
        "project_id": "project-c15-wire",
        "document_id": DOC_ID,
        "source_sha256": SOURCE_SHA,
        "revision_id": REVISION_ID,
        "current_revision_id": REVISION_ID,
        "selected_pages": (0,),
        "owned_viewport_ids": (VIEWPORT_ID,),
        "evidence_snapshot_id": "snapshot-c15-wire",
        "owned_page_numbers": (1,),
        "viewport_page_ownership": ((VIEWPORT_ID, 1),),
    }
    values.update(overrides)
    return ProviderContext(**values)


def _document(*evidence_ids: str) -> DocumentEvidence:
    ids = evidence_ids or ("ev-area", "ev-ceiling")
    return DocumentEvidence(
        document_id=DOC_ID,
        source_sha256=SOURCE_SHA,
        page_count=1,
        page_ids=(PAGE_ID,),
        evidence_ids=tuple(ids),
        producer="synthetic-c15-wire",
        producer_version="1",
    )


def _viewport(**overrides) -> ViewportEvidence:
    values = {
        "viewport_id": VIEWPORT_ID,
        "document_id": DOC_ID,
        "page_id": PAGE_ID,
        "bbox": (0.0, 0.0, 600.0, 800.0),
        "view_type": "floor_plan",
        "status": ViewportResolutionStatus.RESOLVED,
        "evidence_ids": ("ev-area", "ev-ceiling"),
        "confidence": 1.0,
    }
    values.update(overrides)
    return ViewportEvidence(**values)


def _area_quantity(
    *,
    quantity_id: str = "qty-area-room-1",
    value: float = 42.375,
    family: str = "room_area",
    scope_id: str = SCOPE_ID,
    status: str = AuthorityStatus.FIRM.value,
    viewport_id: str = VIEWPORT_ID,
    revision_id: str = REVISION_ID,
    source_sha256: str = SOURCE_SHA,
    page_no: int = 1,
    evidence_id: str = "ev-area",
) -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id=quantity_id,
        family=family,
        semantic_key=f"{family}:{scope_id}",
        value=value,
        unit="m2",
        input_entity_ids=(scope_id,),
        formula="synthetic_authoritative_area",
        formula_version="1",
        evidence_ids=(evidence_id,),
        authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        status=status,
        confidence=0.99,
        metadata={
            "source_sha256": source_sha256,
            "revision_id": revision_id,
            "page_no": page_no,
            "viewport_id": viewport_id,
        },
    )


def _resolve(
    *,
    areas: tuple[QuantityEvidence, ...] | None = None,
    finish_atoms: tuple[EvidenceAtom, ...] | None = None,
    page_text: str | None = None,
    context: ProviderContext | None = None,
    document: DocumentEvidence | None = None,
    viewport: ViewportEvidence | None = None,
    page_no: int = 1,
):
    area_list = (_area_quantity(),) if areas is None else areas
    if finish_atoms is None:
        if page_text is None:
            page_text = "CEILING FINISH: 12mm gypsum plasterboard"
        finish_atoms = collect_explicit_ceiling_finish_atoms(
            page_text=page_text,
            scope_entity_id=SCOPE_ID,
            document_id=DOC_ID,
            page_id=PAGE_ID,
            viewport_id=VIEWPORT_ID,
            method="native_pdf_text",
        )
    evidence_ids = tuple(
        dict.fromkeys(
            [
                *(eid for a in area_list for eid in a.evidence_ids),
                *(atom.evidence_id for atom in finish_atoms),
            ]
        )
    )
    return resolve_ceiling_lining_shadow(
        authoritative_area_quantities=area_list,
        finish_evidence_atoms=finish_atoms,
        context=context or _context(),
        document=document or _document(*evidence_ids),
        viewport=viewport or _viewport(),
        page_no=page_no,
    )


def test_authoritative_area_plus_explicit_finish_yields_shadow_provisional() -> None:
    bag = _resolve()
    records = shadow_quantity_records(bag)
    assert bag["status"] == "shadow_quantities"
    assert bag["shadow_only"] is True
    assert bag["commercial_projection_allowed"] is False
    assert len(records) == 1
    qty = records[0]
    assert qty.value == 42.375
    assert qty.value == _area_quantity().value
    assert qty.family == "ceiling_lining"
    assert qty.status == AuthorityStatus.PROVISIONAL.value
    assert qty.status != AuthorityStatus.FIRM.value
    assert qty.abstained is False
    assert qty.metadata["shadow_only"] is True


def test_output_equals_upstream_area_exactly() -> None:
    area = _area_quantity(value=91.25)
    bag = _resolve(areas=(area,))
    qty = shadow_quantity_records(bag)[0]
    assert qty.value == area.value == 91.25


def test_missing_finish_abstains() -> None:
    bag = _resolve(finish_atoms=())
    qty = shadow_quantity_records(bag)[0]
    assert qty.abstained is True
    assert qty.value is None
    assert "missing_explicit_ceiling_finish" in qty.blocking_reasons


def test_missing_area_abstains() -> None:
    bag = resolve_ceiling_lining_shadow(
        authoritative_area_quantities=(),
        finish_evidence_atoms=collect_explicit_ceiling_finish_atoms(
            page_text="CEILING LINING: chipboard on brandering",
            scope_entity_id=SCOPE_ID,
            document_id=DOC_ID,
            page_id=PAGE_ID,
            viewport_id=VIEWPORT_ID,
        ),
        context=_context(),
        document=_document("ev-ceiling"),
        viewport=_viewport(),
        page_no=1,
    )
    assert bag["status"] == "abstained"
    assert bag["reason"] == "missing_authoritative_area_quantity"
    assert shadow_quantity_records(bag) == ()


def test_height_text_and_rcp_only_are_not_finish_evidence() -> None:
    assert collect_explicit_ceiling_finish_atoms(
        page_text="ceiling height 2700mm\nRCP refer notes",
        scope_entity_id=SCOPE_ID,
        document_id=DOC_ID,
        page_id=PAGE_ID,
        viewport_id=VIEWPORT_ID,
    ) == ()
    bag = _resolve(page_text="ceiling height 2700mm\nRCP")
    qty = shadow_quantity_records(bag)[0]
    assert qty.abstained is True
    assert "missing_explicit_ceiling_finish" in qty.blocking_reasons


def test_unresolved_schedule_reference_abstains() -> None:
    atoms = collect_explicit_ceiling_finish_atoms(
        page_text="CEILING FINISH: refer to schedule",
        scope_entity_id=SCOPE_ID,
        document_id=DOC_ID,
        page_id=PAGE_ID,
        viewport_id=VIEWPORT_ID,
    )
    assert atoms == ()


def test_scope_mismatch_abstains() -> None:
    finish = collect_explicit_ceiling_finish_atoms(
        page_text="CEILING FINISH: gypsum board",
        scope_entity_id="room-OTHER",
        document_id=DOC_ID,
        page_id=PAGE_ID,
        viewport_id=VIEWPORT_ID,
    )
    bag = _resolve(finish_atoms=finish)
    qty = shadow_quantity_records(bag)[0]
    assert qty.abstained is True
    assert "missing_explicit_ceiling_finish" in qty.blocking_reasons


def test_viewport_mismatch_abstains() -> None:
    finish = collect_explicit_ceiling_finish_atoms(
        page_text="CEILING FINISH: gypsum board",
        scope_entity_id=SCOPE_ID,
        document_id=DOC_ID,
        page_id=PAGE_ID,
        viewport_id="vp-OTHER",
    )
    bag = _resolve(
        finish_atoms=finish,
        document=_document("ev-area", finish[0].evidence_id),
    )
    qty = shadow_quantity_records(bag)[0]
    assert qty.abstained is True
    assert "finish_coordinate_frame_mismatch" in qty.blocking_reasons


def test_page_mismatch_abstains() -> None:
    finish = collect_explicit_ceiling_finish_atoms(
        page_text="CEILING FINISH: gypsum board",
        scope_entity_id=SCOPE_ID,
        document_id=DOC_ID,
        page_id="page-OTHER",
        viewport_id=VIEWPORT_ID,
    )
    bag = _resolve(
        finish_atoms=finish,
        document=_document("ev-area", finish[0].evidence_id),
    )
    qty = shadow_quantity_records(bag)[0]
    assert qty.abstained is True
    assert "finish_page_mismatch" in qty.blocking_reasons


def test_source_and_revision_mismatch_abstain() -> None:
    bad_sha = _area_quantity(source_sha256="c" * 64)
    bag = _resolve(areas=(bad_sha,))
    assert shadow_quantity_records(bag)[0].abstained is True
    assert (
        "upstream_area_source_sha256_mismatch"
        in shadow_quantity_records(bag)[0].blocking_reasons
    )

    bad_rev = _area_quantity(revision_id="rev-OLD")
    bag2 = _resolve(areas=(bad_rev,))
    assert shadow_quantity_records(bag2)[0].abstained is True
    assert (
        "upstream_area_revision_mismatch"
        in shadow_quantity_records(bag2)[0].blocking_reasons
    )


def test_conflicting_finishes_abstain() -> None:
    a = collect_explicit_ceiling_finish_atoms(
        page_text="CEILING FINISH: gypsum board",
        scope_entity_id=SCOPE_ID,
        document_id=DOC_ID,
        page_id=PAGE_ID,
        viewport_id=VIEWPORT_ID,
    )
    b = collect_explicit_ceiling_finish_atoms(
        page_text="CEILING FINISH: timber lining",
        scope_entity_id=SCOPE_ID,
        document_id=DOC_ID,
        page_id=PAGE_ID,
        viewport_id=VIEWPORT_ID,
    )
    bag = _resolve(finish_atoms=a + b)
    qty = shadow_quantity_records(bag)[0]
    assert qty.abstained is True
    assert "conflicting_explicit_ceiling_finishes" in qty.blocking_reasons


def test_competing_authoritative_areas_for_same_scope_abstain() -> None:
    a1 = _area_quantity(quantity_id="qty-a1", value=40.0, evidence_id="ev-area-1")
    a2 = _area_quantity(quantity_id="qty-a2", value=41.0, evidence_id="ev-area-2")
    bag = _resolve(areas=(a1, a2))
    qty = shadow_quantity_records(bag)[0]
    assert qty.abstained is True
    assert qty.value is None
    assert "competing_authoritative_area_quantities" in qty.blocking_reasons


def test_unrelated_extra_evidence_cannot_change_result() -> None:
    base = _resolve()
    unrelated = EvidenceAtom(
        evidence_id="ev-noise",
        document_id=DOC_ID,
        page_id=PAGE_ID,
        kind="ceiling_finish",
        method="native_pdf_text",
        viewport_id=VIEWPORT_ID,
        raw_text="CEILING FINISH: gypsum board",
        confidence=0.99,
        status=EvidenceResolutionStatus.RAW,
        metadata={"scope_entity_id": "room-UNRELATED"},
    )
    finish = collect_explicit_ceiling_finish_atoms(
        page_text="CEILING FINISH: 12mm gypsum plasterboard",
        scope_entity_id=SCOPE_ID,
        document_id=DOC_ID,
        page_id=PAGE_ID,
        viewport_id=VIEWPORT_ID,
    )
    noisy = _resolve(
        finish_atoms=finish + (unrelated,),
        document=_document("ev-area", finish[0].evidence_id, "ev-noise"),
    )
    assert shadow_quantity_records(base)[0].value == shadow_quantity_records(noisy)[0].value
    assert (
        shadow_quantity_records(base)[0].quantity_id
        == shadow_quantity_records(noisy)[0].quantity_id
    )


def test_input_order_permutation_and_replay_are_stable() -> None:
    finish = collect_explicit_ceiling_finish_atoms(
        page_text="CEILING FINISH: 12mm gypsum plasterboard",
        scope_entity_id=SCOPE_ID,
        document_id=DOC_ID,
        page_id=PAGE_ID,
        viewport_id=VIEWPORT_ID,
    )
    area = _area_quantity()
    first = _resolve(areas=(area,), finish_atoms=finish)
    second = _resolve(areas=(area,), finish_atoms=tuple(reversed(finish)))
    replay = _resolve(areas=(area,), finish_atoms=finish)
    assert shadow_quantity_records(first)[0].quantity_id == shadow_quantity_records(second)[0].quantity_id
    assert shadow_quantity_records(first)[0].quantity_id == shadow_quantity_records(replay)[0].quantity_id
    assert shadow_quantity_records(first)[0].value == shadow_quantity_records(replay)[0].value


def test_weaker_or_contradictory_evidence_cannot_strengthen() -> None:
    strong = _resolve()
    assert shadow_quantity_records(strong)[0].abstained is False

    ocr_only = collect_explicit_ceiling_finish_atoms(
        page_text="CEILING FINISH: 12mm gypsum plasterboard",
        scope_entity_id=SCOPE_ID,
        document_id=DOC_ID,
        page_id=PAGE_ID,
        viewport_id=VIEWPORT_ID,
        method="ocr_raster_text",
    )
    weak = _resolve(finish_atoms=ocr_only)
    assert shadow_quantity_records(weak)[0].abstained is True
    assert shadow_quantity_records(weak)[0].status == AuthorityStatus.BLOCKED.value

    removed = _resolve(finish_atoms=())
    assert shadow_quantity_records(removed)[0].abstained is True


def test_no_roof_perimeter_accessory_or_wastage_families() -> None:
    qty = shadow_quantity_records(_resolve())[0]
    forbidden = {
        "roof_area",
        "ceiling_perimeter_trim",
        "recessed_fixture_accessories",
        "commercial_wastage",
    }
    assert qty.family == "ceiling_lining"
    assert forbidden.isdisjoint({qty.family})
    deps = qty.metadata.get("dependent_claims_not_evaluated", ())
    assert "roof_area" in deps
    assert "ceiling_perimeter_trim" in deps
    assert "commercial_wastage" in deps


def test_live_predictions_unchanged_by_shadow_adapter(tmp_path: Path) -> None:
    pdf_path = tmp_path / "wire-live.pdf"
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    page.insert_text((40, 40), "SCALE 1:100 FLOOR PLAN")
    page.insert_text((40, 80), "CEILING FINISH: gypsum board")
    page.draw_rect(fitz.Rect(50, 120, 250, 280))
    doc.save(pdf_path)
    doc.close()

    extractor = GenericPlanReaderExtractor()
    before = extractor.extract_from_pdf(str(pdf_path))
    before_tags = sorted(p.tag for p in before)
    before_payload = [p.to_dict() for p in before]

    # Shadow path runs beside live extract; must not mutate extractor predictions.
    area = _area_quantity()
    finish = collect_explicit_ceiling_finish_atoms(
        page_text="CEILING FINISH: gypsum board",
        scope_entity_id=SCOPE_ID,
        document_id=DOC_ID,
        page_id=PAGE_ID,
        viewport_id=VIEWPORT_ID,
    )
    bag = _resolve(areas=(area,), finish_atoms=finish)
    assert bag["shadow_only"] is True
    assert "ceiling_lining" not in before_tags

    after = extractor.extract_from_pdf(str(pdf_path))
    assert sorted(p.tag for p in after) == before_tags
    assert [p.to_dict() for p in after] == before_payload
    assert all(p.tag != "ceiling_lining" for p in after)


def test_commercial_projection_blocked_for_shadow_quantity() -> None:
    qty = shadow_quantity_records(_resolve())[0]
    assert qty.metadata.get("commercial_projection_allowed") is False
    assert qty.metadata.get("shadow_only") is True
    # Shadow ceiling quantities must not silently publish without commercial authority.
    with pytest.raises(MissingCommercialAuthorityError):
        quantity_evidence_to_takeoff_output_row(qty, trace=None, authority=None)


def test_empty_shadow_bag_helper() -> None:
    bag = empty_ceiling_lining_shadow(reason="not_collected")
    assert bag["status"] == "abstained"
    assert bag["quantities"] == []
    assert bag["shadow_only"] is True
