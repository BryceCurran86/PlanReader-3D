"""C15 Phase C remediation: sealed scope proofs from RoomCandidate only.

Gold-free. Proves caller-built proofs and arbitrary room polygon maps cannot
establish ceiling-finish ownership; binding requires resolver-minted proofs
from owned ``RoomCandidate`` geometry.
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
    resolve_ceiling_finish_scope_proofs,
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
from pb_wall_room_topology_contracts import RoomCandidate


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


def _room(
    room_ref: str,
    polygon_pdf_pts: tuple[tuple[float, float], ...],
    *,
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CANDIDATE,
    source_page: int = 1,
    document_id: str = DOC_ID,
    viewport_id: str = VIEWPORT_ID,
) -> RoomCandidate:
    return RoomCandidate(
        room_ref=room_ref,
        label=room_ref,
        polygon_pdf_pts=polygon_pdf_pts,
        polygon_m=None,
        floor_area_m2=None,
        area_page_pts2=10000.0,
        perimeter_m=None,
        geometry_confidence=0.9,
        evidence=(f"ev-room-{room_ref}",),
        source_page=source_page,
        drawing_number="",
        scale_source="topology",
        calibration_confidence=0.0,
        has_voids=False,
        document_id=document_id,
        viewport_id=viewport_id,
        status=status,
    )


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
    assert atom.bbox == (100.0, 100.0, 220.0, 120.0)


def test_adversarial_same_note_room_a_and_room_b_blocked_without_rooms() -> None:
    candidates = _unscoped_candidates(
        text_geometry=({"raw_text": PAGE_NOTE, "bbox": (40.0, 40.0, 80.0, 60.0)},)
    )
    context = _context()
    viewport = _viewport()
    doc = _document(*(atom.evidence_id for atom in candidates))
    proofs = resolve_ceiling_finish_scope_proofs(
        candidates=candidates,
        rooms=(),
        context=context,
        document=doc,
        viewport=viewport,
        page_no=1,
    )
    assert proofs == ()
    scoped_a = bind_unscoped_finish_candidates_to_room(
        candidates=candidates,
        queried_room_ref=ROOM_A,
        proofs=proofs,
        context=context,
        document=doc,
        viewport=viewport,
        page_no=1,
    )
    scoped_b = bind_unscoped_finish_candidates_to_room(
        candidates=candidates,
        queried_room_ref=ROOM_B,
        proofs=proofs,
        context=context,
        document=doc,
        viewport=viewport,
        page_no=1,
    )
    assert scoped_a == () and scoped_b == ()

    area_a = _area(scope_id=ROOM_A, quantity_id="qty-a")
    area_b = _area(scope_id=ROOM_B, quantity_id="qty-b", value=18.0)
    full_doc = _document(
        *(area_a.evidence_ids + area_b.evidence_ids + tuple(a.evidence_id for a in candidates))
    )
    qty_a = build_ceiling_lining_quantity(
        scope_entity_id=ROOM_A,
        area_quantity=area_a,
        finish_evidence_atoms=scoped_a,
        context=context,
        document=full_doc,
        viewport=viewport,
        page_no=1,
    )
    qty_b = build_ceiling_lining_quantity(
        scope_entity_id=ROOM_B,
        area_quantity=area_b,
        finish_evidence_atoms=scoped_b,
        context=context,
        document=full_doc,
        viewport=viewport,
        page_no=1,
    )
    assert qty_a.abstained and qty_b.abstained
    assert "missing_explicit_ceiling_finish" in qty_a.blocking_reasons
    assert "missing_explicit_ceiling_finish" in qty_b.blocking_reasons


def test_caller_constructed_proof_is_rejected() -> None:
    candidates = _unscoped_candidates(
        text_geometry=({"raw_text": PAGE_NOTE, "bbox": (40.0, 40.0, 80.0, 60.0)},)
    )
    context = _context()
    viewport = _viewport()
    doc = _document(*(atom.evidence_id for atom in candidates))
    forged = CeilingFinishScopeProof(
        proof_id="forged",
        finish_evidence_id=candidates[0].evidence_id,
        room_entity_id=ROOM_A,
        proof_kind="owned_scope_link_atom",
        document_id=DOC_ID,
        source_sha256=SOURCE_SHA,
        revision_id=REVISION_ID,
        page_id=PAGE_ID,
        page_no=1,
        viewport_id=VIEWPORT_ID,
        proof_evidence_ids=("link:forged", candidates[0].evidence_id),
    )
    assert forged.is_resolver_minted is False
    scoped = bind_unscoped_finish_candidates_to_room(
        candidates=candidates,
        queried_room_ref=ROOM_A,
        proofs=(forged,),
        context=context,
        document=doc,
        viewport=viewport,
        page_no=1,
    )
    assert scoped == ()


def test_room_candidate_geometry_binds_only_owning_room() -> None:
    candidates = _unscoped_candidates(
        text_geometry=({"raw_text": PAGE_NOTE, "bbox": (40.0, 40.0, 80.0, 60.0)},)
    )
    rooms = (
        _room(ROOM_A, ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0))),
        _room(ROOM_B, ((200.0, 0.0), (300.0, 0.0), (300.0, 100.0), (200.0, 100.0))),
    )
    context = _context()
    viewport = _viewport()
    doc = _document(*(atom.evidence_id for atom in candidates))
    proofs = resolve_ceiling_finish_scope_proofs(
        candidates=candidates,
        rooms=rooms,
        context=context,
        document=doc,
        viewport=viewport,
        page_no=1,
    )
    assert len(proofs) == 1
    assert proofs[0].is_resolver_minted is True
    assert proofs[0].room_entity_id == ROOM_A
    assert proofs[0].document_id == DOC_ID
    assert proofs[0].source_sha256 == SOURCE_SHA
    assert proofs[0].revision_id == REVISION_ID
    assert proofs[0].viewport_id == VIEWPORT_ID

    scoped_a = bind_unscoped_finish_candidates_to_room(
        candidates=candidates,
        queried_room_ref=ROOM_A,
        proofs=proofs,
        context=context,
        document=doc,
        viewport=viewport,
        page_no=1,
    )
    scoped_b = bind_unscoped_finish_candidates_to_room(
        candidates=candidates,
        queried_room_ref=ROOM_B,
        proofs=proofs,
        context=context,
        document=doc,
        viewport=viewport,
        page_no=1,
    )
    assert len(scoped_a) == 1
    assert scoped_a[0].metadata["scope_entity_id"] == ROOM_A
    assert scoped_b == ()


def test_ambiguous_overlapping_room_candidates_yield_no_proof() -> None:
    candidates = _unscoped_candidates(
        text_geometry=({"raw_text": PAGE_NOTE, "bbox": (90.0, 40.0, 110.0, 60.0)},)
    )
    rooms = (
        _room(ROOM_A, ((0.0, 0.0), (120.0, 0.0), (120.0, 100.0), (0.0, 100.0))),
        _room(ROOM_B, ((80.0, 0.0), (200.0, 0.0), (200.0, 100.0), (80.0, 100.0))),
    )
    proofs = resolve_ceiling_finish_scope_proofs(
        candidates=candidates,
        rooms=rooms,
        context=_context(),
        document=_document(*(atom.evidence_id for atom in candidates)),
        viewport=_viewport(),
        page_no=1,
    )
    assert proofs == ()


def test_mismatched_room_document_or_viewport_is_ignored() -> None:
    candidates = _unscoped_candidates(
        text_geometry=({"raw_text": PAGE_NOTE, "bbox": (40.0, 40.0, 80.0, 60.0)},)
    )
    foreign = _room(
        ROOM_A,
        ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)),
        document_id="other-doc",
    )
    proofs = resolve_ceiling_finish_scope_proofs(
        candidates=candidates,
        rooms=(foreign,),
        context=_context(),
        document=_document(*(atom.evidence_id for atom in candidates)),
        viewport=_viewport(),
        page_no=1,
    )
    assert proofs == ()


def test_provider_positive_path_via_room_candidates() -> None:
    candidates = _unscoped_candidates(
        text_geometry=({"raw_text": PAGE_NOTE, "bbox": (40.0, 40.0, 80.0, 60.0)},)
    )
    area = _area(scope_id=ROOM_A)
    rooms = (
        _room(ROOM_A, ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0))),
    )
    doc = _document(*(area.evidence_ids + (candidates[0].evidence_id,)))
    provider = CeilingLiningShadowProvider(
        inputs=CeilingLiningShadowInputs(
            document=doc,
            viewport=_viewport(),
            page_no=1,
            authoritative_area_quantities=(area,),
            unscoped_finish_candidates=candidates,
            rooms=rooms,
        )
    )
    context = _context()
    result = provider.extract(context)
    assert_provider_result_binding(result, provider.descriptor(), context)
    assert len(result.quantities) == 1
    qty = result.quantities[0]
    assert qty.abstained is False
    assert qty.value == area.value
    assert qty.status == AuthorityStatus.PROVISIONAL.value
    assert qty.metadata["shadow_only"] is True


def test_provider_blocks_without_canonical_rooms() -> None:
    candidates = _unscoped_candidates(
        text_geometry=({"raw_text": PAGE_NOTE, "bbox": (40.0, 40.0, 80.0, 60.0)},)
    )
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
            rooms=(),
        )
    )
    result = provider.extract(_context())
    assert len(result.quantities) == 2
    for qty in result.quantities:
        assert qty.abstained is True
        assert qty.status == AuthorityStatus.BLOCKED.value
        assert "missing_explicit_ceiling_finish" in qty.blocking_reasons


def test_provider_inputs_reject_scope_proofs_kwarg() -> None:
    with pytest.raises(TypeError):
        CeilingLiningShadowInputs(
            document=_document(),
            viewport=_viewport(),
            page_no=1,
            authoritative_area_quantities=(),
            unscoped_finish_candidates=(),
            scope_proofs=(),  # type: ignore[call-arg]
        )


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
