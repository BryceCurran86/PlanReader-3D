"""C15 Phase C remediation: authenticated topology only; caller segments BLOCKED.

Gold-free. Proves:
- caller-built proofs / RoomCandidate bodies cannot establish ownership
- diagnostic ``collect_topology_from_segments`` (caller-supplied segments) is
  explicitly non-authoritative for C15 even when collector-sealed
- without an authenticated/source-owned geometry seam listed in
  ``C15_ROOM_INDEX_GEOMETRY_SOURCES``, binding stays fail-closed (BLOCKED)
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import fitz
import pytest

from pb_ceiling_lining_finish_evidence import collect_unscoped_ceiling_finish_candidates
from pb_ceiling_lining_quantity import build_ceiling_lining_quantity
from pb_ceiling_lining_scope_binder import (
    C15_ROOM_INDEX_GEOMETRY_SOURCES,
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
    GEOMETRY_SOURCE_CALLER_SUPPLIED_SEGMENTS,
    GEOMETRY_SOURCE_PAGE_NATIVE_EXTRACT,
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


def _caller_segment_snapshot(segments=_rectangle()) -> TopologySnapshot:
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
    assert snapshot.geometry_source == GEOMETRY_SOURCE_CALLER_SUPPLIED_SEGMENTS
    return snapshot


def _synthetic_room(
    room_ref: str,
    polygon_pdf_pts: tuple[tuple[float, float], ...],
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
        source_page=1,
        drawing_number="",
        scale_source="topology",
        calibration_confidence=0.0,
        has_voids=False,
        document_id=DOC_ID,
        viewport_id=VIEWPORT_ID,
        status=EvidenceResolutionStatus.CANDIDATE,
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


def test_c15_geometry_sources_exclude_caller_segments_until_auth_seam() -> None:
    assert GEOMETRY_SOURCE_CALLER_SUPPLIED_SEGMENTS not in C15_ROOM_INDEX_GEOMETRY_SOURCES
    # Fail closed until an authenticated document/source-bound seam is wired.
    assert C15_ROOM_INDEX_GEOMETRY_SOURCES == frozenset()


def test_caller_segment_collector_snapshot_cannot_mint_room_index() -> None:
    snapshot = _caller_segment_snapshot()
    assert snapshot.is_collector_produced is True
    assert len(snapshot.rooms) >= 1
    assert build_owned_topology_room_index(snapshot=snapshot, context=_context()) is None


def test_page_native_tagged_snapshot_still_blocked_without_eligible_source() -> None:
    """Page-native tag alone is not enough until C15 lists that source."""
    snapshot = collect_topology_from_segments(
        _rectangle(),
        document_id=DOC_ID,
        page_id=PAGE_ID,
        page_number=1,
        viewport_id=VIEWPORT_ID,
        viewport_authority="resolved_floor_plan",
        evaluate_opening_hosts=False,
        bind_room_labels=False,
        geometry_source=GEOMETRY_SOURCE_PAGE_NATIVE_EXTRACT,
    )
    assert snapshot.geometry_source == GEOMETRY_SOURCE_PAGE_NATIVE_EXTRACT
    assert snapshot.is_collector_produced is True
    # Eligible set empty → still fail closed (no trust shortcut).
    assert build_owned_topology_room_index(snapshot=snapshot, context=_context()) is None


def test_adversarial_same_note_blocked_without_authenticated_topology() -> None:
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

    forged_index = OwnedTopologyRoomIndex(
        index_id="forged-index",
        document_id=DOC_ID,
        source_sha256=SOURCE_SHA,
        revision_id=REVISION_ID,
        page_id=PAGE_ID,
        page_no=1,
        viewport_id=VIEWPORT_ID,
        topology_snapshot_fingerprint="forged",
        geometry_source=GEOMETRY_SOURCE_CALLER_SUPPLIED_SEGMENTS,
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
    forged_index = OwnedTopologyRoomIndex(
        index_id="forged-index",
        document_id=DOC_ID,
        source_sha256=SOURCE_SHA,
        revision_id=REVISION_ID,
        page_id=PAGE_ID,
        page_no=1,
        viewport_id=VIEWPORT_ID,
        topology_snapshot_fingerprint="forged",
        geometry_source="page_native_extract",
        _rooms_by_ref={},
    )
    forged = CeilingFinishScopeProof(
        proof_id="forged",
        finish_evidence_id=candidates[0].evidence_id,
        room_entity_id="room-A",
        proof_kind="owned_scope_link_atom",
        document_id=DOC_ID,
        source_sha256=SOURCE_SHA,
        revision_id=REVISION_ID,
        page_id=PAGE_ID,
        page_no=1,
        viewport_id=VIEWPORT_ID,
        topology_index_id=forged_index.index_id,
        proof_evidence_ids=("link:forged", candidates[0].evidence_id),
    )
    assert forged.is_resolver_minted is False
    scoped = bind_unscoped_finish_candidates_to_room(
        candidates=candidates,
        queried_room_ref="room-A",
        proofs=(forged,),
        room_index=forged_index,
        document=_document(*(atom.evidence_id for atom in candidates)),
        viewport=_viewport(),
    )
    assert scoped == ()


def test_caller_constructed_room_candidate_cannot_mint_index() -> None:
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
        geometry_source=GEOMETRY_SOURCE_CALLER_SUPPLIED_SEGMENTS,
    )
    assert free_snapshot.is_collector_produced is False
    assert build_owned_topology_room_index(snapshot=free_snapshot, context=_context()) is None

    sealed = _caller_segment_snapshot()
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


def test_provider_blocks_on_caller_segment_topology_snapshot() -> None:
    snapshot = _caller_segment_snapshot()
    room_ref = snapshot.rooms[0].room_ref if snapshot.rooms else "room-A"
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
    result = provider.extract(_context())
    assert_provider_result_binding(result, provider.descriptor(), _context())
    assert len(result.quantities) == 1
    qty = result.quantities[0]
    assert qty.abstained is True
    assert qty.status == AuthorityStatus.BLOCKED.value
    assert "missing_explicit_ceiling_finish" in qty.blocking_reasons


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
