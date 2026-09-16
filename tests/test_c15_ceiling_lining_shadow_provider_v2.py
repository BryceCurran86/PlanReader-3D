"""C15 Phase C remediation: producer-owned topology index, not caller rooms.

Gold-free. Proves caller-built proofs, free ``RoomCandidate`` bodies, and
unsealed / mutated ``TopologySnapshot`` records cannot establish
ceiling-finish ownership. Binding requires resolver-minted proofs from an
``OwnedTopologyRoomIndex`` sealed from collector-produced topology.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import fitz
import pytest

from pb_ceiling_lining_finish_evidence import collect_unscoped_ceiling_finish_candidates
from pb_ceiling_lining_quantity import build_ceiling_lining_quantity
from pb_ceiling_lining_scope_binder import (
    CeilingFinishScopeProof,
    OwnedTopologyRoomIndex,
    bind_unscoped_finish_candidates_to_room,
    build_owned_topology_room_index,
    resolve_ceiling_finish_scope_proofs,
)
from pb_ceiling_lining_shadow_provider import (
    PROVIDER_ENGINE_ID,
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
from pb_wall_topology_diagnostics import (
    TopologySnapshot,
    collect_topology_from_segments,
)


SOURCE_SHA = "c" * 64
DOC_ID = "doc-c15-v2"
PAGE_ID = "page-1"
VIEWPORT_ID = "vp-floor-1"
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


def _seg(seg_id, x1, y1, x2, y2, **overrides):
    base = {
        "id": seg_id,
        "kind": "line",
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "width": 1.0,
        "stroke": (0, 0, 0),
        "fill": None,
        "layer": "",
        "dashes": "",
    }
    base.update(overrides)
    return base


def _rectangle(origin=(0.0, 0.0), width=100.0, height=100.0, prefix="r"):
    x0, y0 = origin
    x1, y1 = x0 + width, y0 + height
    return [
        _seg(f"{prefix}0", x0, y0, x1, y0),
        _seg(f"{prefix}1", x1, y0, x1, y1),
        _seg(f"{prefix}2", x1, y1, x0, y1),
        _seg(f"{prefix}3", x0, y1, x0, y0),
    ]


def _sealed_snapshot(segments) -> TopologySnapshot:
    snapshot = collect_topology_from_segments(
        segments,
        document_id=DOC_ID,
        page_id=PAGE_ID,
        page_number=1,
        viewport_id=VIEWPORT_ID,
        evaluate_opening_hosts=False,
        bind_room_labels=False,
    )
    assert snapshot.is_collector_produced is True
    return snapshot


def _owned_index(snapshot: TopologySnapshot) -> OwnedTopologyRoomIndex:
    index = build_owned_topology_room_index(snapshot=snapshot, context=_context())
    assert index is not None
    assert index.is_producer_owned is True
    return index


def _synthetic_room(
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


def test_adversarial_same_note_blocked_without_producer_topology() -> None:
    candidates = _unscoped_candidates(
        text_geometry=({"raw_text": PAGE_NOTE, "bbox": (40.0, 40.0, 80.0, 60.0)},)
    )
    viewport = _viewport()
    doc = _document(*(atom.evidence_id for atom in candidates))
    proofs = resolve_ceiling_finish_scope_proofs(
        candidates=candidates,
        room_index=None,
        document=doc,
        viewport=viewport,
    )
    assert proofs == ()

    # No producer-owned index: cannot bind even with a queried room_ref.
    forged_index = OwnedTopologyRoomIndex(
        index_id="forged-index",
        document_id=DOC_ID,
        source_sha256=SOURCE_SHA,
        revision_id=REVISION_ID,
        page_id=PAGE_ID,
        page_no=1,
        viewport_id=VIEWPORT_ID,
        topology_snapshot_fingerprint="forged",
        _rooms_by_ref={},
    )
    assert forged_index.is_producer_owned is False
    scoped = bind_unscoped_finish_candidates_to_room(
        candidates=candidates,
        queried_room_ref="room-A",
        proofs=proofs,
        room_index=forged_index,
        document=doc,
        viewport=viewport,
    )
    assert scoped == ()

    area_a = _area(scope_id="room-A", quantity_id="qty-a")
    area_b = _area(scope_id="room-B", quantity_id="qty-b", value=18.0)
    full_doc = _document(
        *(area_a.evidence_ids + area_b.evidence_ids + tuple(a.evidence_id for a in candidates))
    )
    context = _context()
    qty_a = build_ceiling_lining_quantity(
        scope_entity_id="room-A",
        area_quantity=area_a,
        finish_evidence_atoms=(),
        context=context,
        document=full_doc,
        viewport=viewport,
        page_no=1,
    )
    qty_b = build_ceiling_lining_quantity(
        scope_entity_id="room-B",
        area_quantity=area_b,
        finish_evidence_atoms=(),
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
    snapshot = _sealed_snapshot(_rectangle())
    room_index = _owned_index(snapshot)
    room_ref = room_index.rooms()[0].room_ref
    viewport = _viewport()
    doc = _document(*(atom.evidence_id for atom in candidates))
    forged = CeilingFinishScopeProof(
        proof_id="forged",
        finish_evidence_id=candidates[0].evidence_id,
        room_entity_id=room_ref,
        proof_kind="owned_scope_link_atom",
        document_id=DOC_ID,
        source_sha256=SOURCE_SHA,
        revision_id=REVISION_ID,
        page_id=PAGE_ID,
        page_no=1,
        viewport_id=VIEWPORT_ID,
        topology_index_id=room_index.index_id,
        proof_evidence_ids=("link:forged", candidates[0].evidence_id),
    )
    assert forged.is_resolver_minted is False
    scoped = bind_unscoped_finish_candidates_to_room(
        candidates=candidates,
        queried_room_ref=room_ref,
        proofs=(forged,),
        room_index=room_index,
        document=doc,
        viewport=viewport,
    )
    assert scoped == ()


def test_caller_constructed_room_candidate_cannot_mint_index() -> None:
    """Synthetic RoomCandidate bodies are not producer-owned topology."""
    synthetic = _synthetic_room(
        "caller-room",
        ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)),
    )
    free_snapshot = TopologySnapshot(
        document_id=DOC_ID,
        page_id=PAGE_ID,
        page_number=1,
        viewport_id=VIEWPORT_ID,
        viewport_authority="caller_supplied",
        rooms=(synthetic,),
    )
    assert free_snapshot.is_collector_produced is False
    assert build_owned_topology_room_index(snapshot=free_snapshot, context=_context()) is None

    # Even replacing rooms onto a sealed snapshot invalidates the seal.
    sealed = _sealed_snapshot(_rectangle())
    assert sealed.is_collector_produced is True
    mutated = replace(sealed, rooms=(synthetic,))
    assert mutated.is_collector_produced is False
    assert build_owned_topology_room_index(snapshot=mutated, context=_context()) is None


def test_resolve_api_rejects_rooms_kwarg() -> None:
    with pytest.raises(TypeError):
        resolve_ceiling_finish_scope_proofs(
            candidates=(),
            rooms=(_synthetic_room("x", ((0, 0), (1, 0), (1, 1)))),  # type: ignore[call-arg]
            document=_document(),
            viewport=_viewport(),
        )


def test_provider_inputs_reject_rooms_kwarg() -> None:
    with pytest.raises(TypeError):
        CeilingLiningShadowInputs(
            document=_document(),
            viewport=_viewport(),
            page_no=1,
            authoritative_area_quantities=(),
            unscoped_finish_candidates=(),
            rooms=(),  # type: ignore[call-arg]
        )


def test_owned_topology_binds_only_owning_room() -> None:
    # Two disjoint rooms; finish bbox center sits only in room A.
    snapshot = _sealed_snapshot(
        _rectangle((0.0, 0.0), 100.0, 100.0, "a")
        + _rectangle((200.0, 0.0), 100.0, 100.0, "b")
    )
    room_index = _owned_index(snapshot)
    rooms = room_index.rooms()
    assert len(rooms) == 2
    room_a = next(r for r in rooms if any(pt[0] < 150 for pt in r.polygon_pdf_pts))
    room_b = next(r for r in rooms if r.room_ref != room_a.room_ref)

    candidates = _unscoped_candidates(
        text_geometry=({"raw_text": PAGE_NOTE, "bbox": (40.0, 40.0, 80.0, 60.0)},)
    )
    viewport = _viewport()
    doc = _document(*(atom.evidence_id for atom in candidates))
    proofs = resolve_ceiling_finish_scope_proofs(
        candidates=candidates,
        room_index=room_index,
        document=doc,
        viewport=viewport,
    )
    assert len(proofs) == 1
    assert proofs[0].is_resolver_minted is True
    assert proofs[0].room_entity_id == room_a.room_ref
    assert proofs[0].topology_index_id == room_index.index_id
    assert proofs[0].document_id == DOC_ID
    assert proofs[0].source_sha256 == SOURCE_SHA
    assert proofs[0].revision_id == REVISION_ID
    assert proofs[0].viewport_id == VIEWPORT_ID

    scoped_a = bind_unscoped_finish_candidates_to_room(
        candidates=candidates,
        queried_room_ref=room_a.room_ref,
        proofs=proofs,
        room_index=room_index,
        document=doc,
        viewport=viewport,
    )
    scoped_b = bind_unscoped_finish_candidates_to_room(
        candidates=candidates,
        queried_room_ref=room_b.room_ref,
        proofs=proofs,
        room_index=room_index,
        document=doc,
        viewport=viewport,
    )
    assert len(scoped_a) == 1
    assert scoped_a[0].metadata["scope_entity_id"] == room_a.room_ref
    assert scoped_a[0].metadata["topology_index_id"] == room_index.index_id
    assert scoped_b == ()


def test_finish_outside_all_owned_rooms_yields_no_proof() -> None:
    snapshot = _sealed_snapshot(_rectangle((0.0, 0.0), 100.0, 100.0, "a"))
    room_index = _owned_index(snapshot)
    candidates = _unscoped_candidates(
        text_geometry=({"raw_text": PAGE_NOTE, "bbox": (400.0, 400.0, 440.0, 420.0)},)
    )
    proofs = resolve_ceiling_finish_scope_proofs(
        candidates=candidates,
        room_index=room_index,
        document=_document(*(atom.evidence_id for atom in candidates)),
        viewport=_viewport(),
    )
    assert proofs == ()


def test_provider_positive_path_via_owned_topology() -> None:
    snapshot = _sealed_snapshot(_rectangle((0.0, 0.0), 100.0, 100.0, "a"))
    room_index = _owned_index(snapshot)
    room_ref = room_index.rooms()[0].room_ref
    candidates = _unscoped_candidates(
        text_geometry=({"raw_text": PAGE_NOTE, "bbox": (40.0, 40.0, 80.0, 60.0)},)
    )
    area = _area(scope_id=room_ref)
    doc = _document(*(area.evidence_ids + (candidates[0].evidence_id,)))
    provider = CeilingLiningShadowProvider(
        inputs=CeilingLiningShadowInputs(
            document=doc,
            viewport=_viewport(),
            page_no=1,
            authoritative_area_quantities=(area,),
            unscoped_finish_candidates=candidates,
            topology_snapshot=snapshot,
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


def test_provider_blocks_without_topology_snapshot() -> None:
    candidates = _unscoped_candidates(
        text_geometry=({"raw_text": PAGE_NOTE, "bbox": (40.0, 40.0, 80.0, 60.0)},)
    )
    area_a = _area(scope_id="room-A", quantity_id="qty-a")
    area_b = _area(scope_id="room-B", quantity_id="qty-b", value=11.0)
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
            topology_snapshot=None,
        )
    )
    result = provider.extract(_context())
    assert len(result.quantities) == 2
    for qty in result.quantities:
        assert qty.abstained is True
        assert qty.status == AuthorityStatus.BLOCKED.value
        assert "missing_explicit_ceiling_finish" in qty.blocking_reasons


def test_provider_blocks_on_unsealed_snapshot_with_synthetic_room() -> None:
    synthetic = _synthetic_room(
        "caller-room",
        ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)),
    )
    free_snapshot = TopologySnapshot(
        document_id=DOC_ID,
        page_id=PAGE_ID,
        page_number=1,
        viewport_id=VIEWPORT_ID,
        viewport_authority="caller_supplied",
        rooms=(synthetic,),
    )
    candidates = _unscoped_candidates(
        text_geometry=({"raw_text": PAGE_NOTE, "bbox": (40.0, 40.0, 80.0, 60.0)},)
    )
    area = _area(scope_id=synthetic.room_ref)
    doc = _document(*(area.evidence_ids + (candidates[0].evidence_id,)))
    provider = CeilingLiningShadowProvider(
        inputs=CeilingLiningShadowInputs(
            document=doc,
            viewport=_viewport(),
            page_no=1,
            authoritative_area_quantities=(area,),
            unscoped_finish_candidates=candidates,
            topology_snapshot=free_snapshot,
        )
    )
    result = provider.extract(_context())
    assert len(result.quantities) == 1
    assert result.quantities[0].abstained is True
    assert "missing_explicit_ceiling_finish" in result.quantities[0].blocking_reasons


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
