"""C15 Phase C rebuild: unscoped finish + independent binder + MigrationProvider.

Gold-free. Proves:
- collection never accepts caller room/scope as proof;
- binder requires independent CeilingFinishScopeProof;
- same page note + Room A / Room B requests stay BLOCKED without proof;
- ProviderResult envelope (descriptor / eligibility / fingerprints);
- #315 quantity contract preserved (authoritative area + explicit finish);
- no live ExtractedPrediction / commercial / FIRM promotion.
"""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pb_ceiling_lining_finish_evidence import collect_unscoped_ceiling_finish_candidates
from pb_ceiling_lining_quantity import build_ceiling_lining_quantity
from pb_ceiling_lining_scope_binder import (
    CeilingFinishScopeProof,
    bind_unscoped_finish_candidates_to_room,
    prove_text_bbox_in_unique_room_face,
)
from pb_ceiling_lining_shadow_provider import (
    PROVIDER_ENGINE_ID,
    PROVIDER_FAMILY,
    CeilingLiningShadowInputs,
    CeilingLiningShadowProvider,
)
from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_migration_contracts import (
    DocumentEvidence,
    EvidenceResolutionStatus,
    QuantityEvidence,
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_migration_provider_envelope import (
    ProviderContext,
    assert_provider_result_binding,
)
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor
from pb_provider_gold_isolation import assert_provider_gold_free


SOURCE_SHA = "c" * 64
DOC_ID = "doc-c15-v2"
PAGE_ID = "page-1"
VIEWPORT_ID = "vp-floor-1"
ROOM_A = "room-A"
ROOM_B = "room-B"
REVISION_ID = "rev-1"
PAGE_NOTE = "CEILING FINISH: 12mm gypsum plasterboard"


def _context(**overrides) -> ProviderContext:
    values = {
        "run_id": "run-c15-v2",
        "workspace_id": "workspace-c15-v2",
        "project_id": "project-c15-v2",
        "document_id": DOC_ID,
        "source_sha256": SOURCE_SHA,
        "revision_id": REVISION_ID,
        "current_revision_id": REVISION_ID,
        "selected_pages": (0,),
        "owned_viewport_ids": (VIEWPORT_ID,),
        "evidence_snapshot_id": "snapshot-c15-v2",
        "owned_page_numbers": (1,),
        "viewport_page_ownership": ((VIEWPORT_ID, 1),),
    }
    values.update(overrides)
    return ProviderContext(**values)


def _document(*evidence_ids: str) -> DocumentEvidence:
    ids = evidence_ids or ("ev-area",)
    return DocumentEvidence(
        document_id=DOC_ID,
        source_sha256=SOURCE_SHA,
        page_count=1,
        page_ids=(PAGE_ID,),
        evidence_ids=tuple(dict.fromkeys(ids)),
        producer="synthetic-c15-v2",
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
        "evidence_ids": ("ev-area",),
        "confidence": 1.0,
    }
    values.update(overrides)
    return ViewportEvidence(**values)


def _area(*, scope_id: str, quantity_id: str = "qty-area", value: float = 42.375) -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id=quantity_id,
        family="room_area",
        semantic_key=f"room_area:{scope_id}",
        value=value,
        unit="m2",
        input_entity_ids=(scope_id,),
        formula="synthetic_authoritative_area",
        formula_version="1",
        evidence_ids=(f"ev-area-{scope_id}",),
        authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        status=AuthorityStatus.FIRM.value,
        confidence=0.99,
        metadata={
            "source_sha256": SOURCE_SHA,
            "revision_id": REVISION_ID,
            "page_no": 1,
            "viewport_id": VIEWPORT_ID,
        },
    )


def _unscoped_candidates(**kwargs):
    values = {
        "page_text": PAGE_NOTE,
        "document_id": DOC_ID,
        "source_sha256": SOURCE_SHA,
        "revision_id": REVISION_ID,
        "page_id": PAGE_ID,
        "page_no": 1,
        "viewport_id": VIEWPORT_ID,
        "method": "native_pdf_text",
    }
    values.update(kwargs)
    return collect_unscoped_ceiling_finish_candidates(**values)


def test_collection_is_unscoped_and_preserves_ownership() -> None:
    atoms = _unscoped_candidates(
        text_geometry=({"raw_text": PAGE_NOTE, "bbox": (100.0, 100.0, 220.0, 120.0)},)
    )
    assert len(atoms) == 1
    atom = atoms[0]
    assert atom.metadata.get("unscoped") is True
    assert "scope_entity_id" not in atom.metadata
    assert atom.metadata["source_sha256"] == SOURCE_SHA
    assert atom.metadata["revision_id"] == REVISION_ID
    assert atom.metadata["page_no"] == 1
    assert atom.bbox == (100.0, 100.0, 220.0, 120.0)
    assert atom.viewport_id == VIEWPORT_ID
    assert atom.document_id == DOC_ID
    assert atom.page_id == PAGE_ID


def test_collection_api_rejects_scope_kwarg() -> None:
    with pytest.raises(TypeError):
        collect_unscoped_ceiling_finish_candidates(
            page_text=PAGE_NOTE,
            document_id=DOC_ID,
            source_sha256=SOURCE_SHA,
            revision_id=REVISION_ID,
            page_id=PAGE_ID,
            page_no=1,
            scope_entity_id=ROOM_A,  # type: ignore[call-arg]
        )


def test_adversarial_same_note_room_a_and_room_b_blocked_without_proof() -> None:
    candidates = _unscoped_candidates()
    assert candidates

    scoped_a = bind_unscoped_finish_candidates_to_room(
        candidates=candidates, room_entity_id=ROOM_A, proofs=()
    )
    scoped_b = bind_unscoped_finish_candidates_to_room(
        candidates=candidates, room_entity_id=ROOM_B, proofs=()
    )
    assert scoped_a == ()
    assert scoped_b == ()

    context = _context()
    viewport = _viewport()
    area_a = _area(scope_id=ROOM_A, quantity_id="qty-a")
    area_b = _area(scope_id=ROOM_B, quantity_id="qty-b", value=18.0)
    doc = _document(
        *(area_a.evidence_ids + area_b.evidence_ids + tuple(a.evidence_id for a in candidates))
    )

    qty_a = build_ceiling_lining_quantity(
        scope_entity_id=ROOM_A,
        area_quantity=area_a,
        finish_evidence_atoms=scoped_a,
        context=context,
        document=doc,
        viewport=viewport,
        page_no=1,
    )
    qty_b = build_ceiling_lining_quantity(
        scope_entity_id=ROOM_B,
        area_quantity=area_b,
        finish_evidence_atoms=scoped_b,
        context=context,
        document=doc,
        viewport=viewport,
        page_no=1,
    )
    assert qty_a.abstained and qty_a.status == AuthorityStatus.BLOCKED.value
    assert qty_b.abstained and qty_b.status == AuthorityStatus.BLOCKED.value
    assert "missing_explicit_ceiling_finish" in qty_a.blocking_reasons
    assert "missing_explicit_ceiling_finish" in qty_b.blocking_reasons
    assert qty_a.value is None and qty_b.value is None


def test_independent_geometry_proof_binds_only_owning_room() -> None:
    candidates = _unscoped_candidates(
        text_geometry=({"raw_text": PAGE_NOTE, "bbox": (40.0, 40.0, 80.0, 60.0)},)
    )
    atom = candidates[0]
    room_faces = {
        ROOM_A: ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)),
        ROOM_B: ((200.0, 0.0), (300.0, 0.0), (300.0, 100.0), (200.0, 100.0)),
    }
    proof = prove_text_bbox_in_unique_room_face(
        finish_evidence_id=atom.evidence_id,
        finish_bbox=atom.bbox,
        room_faces=room_faces,
    )
    assert proof is not None
    assert proof.room_entity_id == ROOM_A

    scoped_a = bind_unscoped_finish_candidates_to_room(
        candidates=candidates, room_entity_id=ROOM_A, proofs=(proof,)
    )
    scoped_b = bind_unscoped_finish_candidates_to_room(
        candidates=candidates, room_entity_id=ROOM_B, proofs=(proof,)
    )
    assert len(scoped_a) == 1
    assert scoped_a[0].metadata["scope_entity_id"] == ROOM_A
    assert scoped_b == ()


def test_ambiguous_room_face_containment_yields_no_proof() -> None:
    candidates = _unscoped_candidates(
        text_geometry=({"raw_text": PAGE_NOTE, "bbox": (90.0, 40.0, 110.0, 60.0)},)
    )
    # Overlapping faces → ambiguous, no unique owner.
    room_faces = {
        ROOM_A: ((0.0, 0.0), (120.0, 0.0), (120.0, 100.0), (0.0, 100.0)),
        ROOM_B: ((80.0, 0.0), (200.0, 0.0), (200.0, 100.0), (80.0, 100.0)),
    }
    proof = prove_text_bbox_in_unique_room_face(
        finish_evidence_id=candidates[0].evidence_id,
        finish_bbox=candidates[0].bbox,
        room_faces=room_faces,
    )
    assert proof is None


def test_provider_result_envelope_and_binding() -> None:
    candidates = _unscoped_candidates(
        text_geometry=({"raw_text": PAGE_NOTE, "bbox": (40.0, 40.0, 80.0, 60.0)},)
    )
    proof = CeilingFinishScopeProof(
        finish_evidence_id=candidates[0].evidence_id,
        room_entity_id=ROOM_A,
        proof_kind="owned_scope_link_atom",
        proof_evidence_ids=("link:room-A:finish", candidates[0].evidence_id),
    )
    area = _area(scope_id=ROOM_A)
    doc = _document(*(area.evidence_ids + (candidates[0].evidence_id,)))
    inputs = CeilingLiningShadowInputs(
        document=doc,
        viewport=_viewport(),
        page_no=1,
        authoritative_area_quantities=(area,),
        unscoped_finish_candidates=candidates,
        scope_proofs=(proof,),
    )
    provider = CeilingLiningShadowProvider(inputs=inputs)
    context = _context()
    assert provider.eligibility(context).eligible is True
    result = provider.extract(context)
    assert result.descriptor.provider_id == PROVIDER_ENGINE_ID
    assert result.descriptor.family == PROVIDER_FAMILY
    assert_provider_result_binding(result, provider.descriptor(), context)
    assert len(result.quantities) == 1
    qty = result.quantities[0]
    assert qty.abstained is False
    assert qty.value == area.value
    assert qty.status == AuthorityStatus.PROVISIONAL.value
    assert qty.status != AuthorityStatus.FIRM.value
    assert qty.metadata["shadow_only"] is True
    assert qty.metadata["commercial_projection_allowed"] is False


def test_provider_blocks_without_independent_proof_for_requested_rooms() -> None:
    candidates = _unscoped_candidates()
    area_a = _area(scope_id=ROOM_A, quantity_id="qty-a")
    area_b = _area(scope_id=ROOM_B, quantity_id="qty-b", value=11.0)
    doc = _document(
        *(
            area_a.evidence_ids
            + area_b.evidence_ids
            + tuple(atom.evidence_id for atom in candidates)
        )
    )
    provider = CeilingLiningShadowProvider(
        inputs=CeilingLiningShadowInputs(
            document=doc,
            viewport=_viewport(),
            page_no=1,
            authoritative_area_quantities=(area_a, area_b),
            unscoped_finish_candidates=candidates,
            scope_proofs=(),
        )
    )
    result = provider.extract(_context())
    assert len(result.quantities) == 2
    for qty in result.quantities:
        assert qty.abstained is True
        assert qty.status == AuthorityStatus.BLOCKED.value
        assert "missing_explicit_ceiling_finish" in qty.blocking_reasons


def test_provider_gold_isolated() -> None:
    assert_provider_gold_free(PROVIDER_ENGINE_ID, "pb_ceiling_lining_shadow_provider")


def test_live_extractor_unchanged_by_shadow_provider(tmp_path: Path) -> None:
    pdf_path = tmp_path / "c15-live.pdf"
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    page.insert_text((40, 40), "SCALE 1:100 FLOOR PLAN")
    page.insert_text((40, 80), PAGE_NOTE)
    page.draw_rect(fitz.Rect(50, 120, 250, 280), color=(0, 0, 0), width=1)
    doc.save(pdf_path)
    doc.close()

    extractor = GenericPlanReaderExtractor()
    preds = extractor.extract_from_pdf(str(pdf_path))
    preds2 = extractor.extract_from_pdf(str(pdf_path))
    assert [p.to_dict() for p in preds2] == [p.to_dict() for p in preds]
    for pred in preds:
        payload = pred.to_dict()
        assert payload.get("family") != "ceiling_lining"
        assert "ceiling_lining" not in str(payload.get("tag", "")).casefold()
