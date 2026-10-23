"""Tests for producer-owned hybrid mixed-format (vector/raster) geometry recovery shadow authority (Item 8)."""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_hybrid_mixed_format_recovery_shadow import (
    COLLOCATED_RASTER_DUPLICATE_RECONCILED,
    HYBRID_PAGE_MODALITY_DETERMINED,
    MODALITY_MIXED_HYBRID,
    MODALITY_PURE_RASTER,
    MODALITY_PURE_VECTOR,
    PURE_RASTER_PRESERVED,
    PURE_VECTOR_PRESERVED,
    RASTER_PRIMITIVE_PROMOTED_AUGMENTATION,
    RASTER_PRIMITIVE_RECONCILED_AS_CORROBORATION,
    SOURCE_HYBRID_RECOVERY_RESOLVED,
    SOURCE_HYBRID_RECOVERY_UNAVAILABLE,
    UNMATCHED_RASTER_PROMOTED,
    VECTOR_PRIMITIVE_CANONICAL,
    SourceHybridMixedFormatRecoveryAuthority,
    SourceHybridMixedFormatRecoveryProducer,
    SourceHybridMixedFormatSelector,
    SourceReconciledHybridPrimitiveRecord,
    reconcile_hybrid_primitives,
)


def _seg(ident, x1, y1, x2, y2):
    return {"id": ident, "x1": float(x1), "y1": float(y1), "x2": float(x2), "y2": float(y2)}


def _make_selector(
    *,
    doc="doc-hybrid",
    rev="rev-01",
    sha="a" * 64,
    snap="snap-01",
    page="1",
) -> SourceHybridMixedFormatSelector:
    return SourceHybridMixedFormatSelector(
        document_id=doc,
        revision_id=rev,
        source_sha256=sha,
        snapshot_id=snap,
        page_id=page,
    )


def test_sealing_raises_permission_error():
    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceHybridMixedFormatRecoveryProducer(object())

    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceHybridMixedFormatRecoveryAuthority(object(), {})

    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceReconciledHybridPrimitiveRecord(
            primitive_id="prim-1",
            source_modality="vector",
            reconciliation_role=VECTOR_PRIMITIVE_CANONICAL,
            x1=0.0,
            y1=0.0,
            x2=10.0,
            y2=0.0,
            corroborating_primitive_ids=(),
            reason_codes=(),
        )


def test_pure_vector_page_reconciliation():
    v_segs = [_seg("v1", 0, 0, 100, 0), _seg("v2", 100, 0, 100, 100)]
    rec = reconcile_hybrid_primitives(v_segs, [])
    assert rec["detected_modality"] == MODALITY_PURE_VECTOR
    assert rec["vector_count"] == 2
    assert rec["raster_count"] == 0
    assert rec["total_reconciled_primitives"] == 2
    for p in rec["reconciled_primitives"]:
        assert p["source_modality"] == "vector"
        assert p["reconciliation_role"] == VECTOR_PRIMITIVE_CANONICAL
        assert PURE_VECTOR_PRESERVED in p["reason_codes"]


def test_pure_raster_page_reconciliation():
    r_segs = [_seg("r1", 0, 0, 100, 0), _seg("r2", 100, 0, 100, 100)]
    rec = reconcile_hybrid_primitives([], r_segs)
    assert rec["detected_modality"] == MODALITY_PURE_RASTER
    assert rec["vector_count"] == 0
    assert rec["raster_count"] == 2
    assert rec["promoted_raster_count"] == 2
    for p in rec["reconciled_primitives"]:
        assert p["source_modality"] == "raster"
        assert p["reconciliation_role"] == RASTER_PRIMITIVE_PROMOTED_AUGMENTATION
        assert PURE_RASTER_PRESERVED in p["reason_codes"]


def test_mixed_hybrid_page_collocated_raster_reconciliation():
    # Vector segment from (0, 0) to (100, 0)
    v_segs = [_seg("v_wall", 0.0, 0.0, 100.0, 0.0)]
    # Collocated raster segment (offset by 0.5 pt perpendicular, within 2.5 pt snap)
    r_segs = [_seg("r_wall_pixel", 0.0, 0.5, 100.0, 0.5)]

    rec = reconcile_hybrid_primitives(v_segs, r_segs, snap_tolerance=2.5)
    assert rec["detected_modality"] == MODALITY_MIXED_HYBRID
    assert rec["vector_count"] == 1
    assert rec["raster_count"] == 1
    assert rec["reconciled_raster_count"] == 1
    assert rec["promoted_raster_count"] == 0

    p_map = {p["primitive_id"]: p for p in rec["reconciled_primitives"]}
    # Vector is canonical and references collocated raster
    assert p_map["v_wall"]["reconciliation_role"] == VECTOR_PRIMITIVE_CANONICAL
    assert p_map["v_wall"]["corroborating_primitive_ids"] == ("r_wall_pixel",)
    assert COLLOCATED_RASTER_DUPLICATE_RECONCILED in p_map["v_wall"]["reason_codes"]

    # Raster is marked as corroboration, preventing duplicate wall edge
    assert p_map["r_wall_pixel"]["reconciliation_role"] == RASTER_PRIMITIVE_RECONCILED_AS_CORROBORATION
    assert COLLOCATED_RASTER_DUPLICATE_RECONCILED in p_map["r_wall_pixel"]["reason_codes"]


def test_mixed_hybrid_page_unmatched_raster_promotion():
    # Vector line at y=0, Raster line at y=50 (far apart: > 2.5 pt)
    v_segs = [_seg("v_grid", 0.0, 0.0, 100.0, 0.0)]
    r_segs = [_seg("r_stamp", 0.0, 50.0, 100.0, 50.0)]

    rec = reconcile_hybrid_primitives(v_segs, r_segs, snap_tolerance=2.5)
    assert rec["detected_modality"] == MODALITY_MIXED_HYBRID
    assert rec["promoted_raster_count"] == 1
    assert rec["reconciled_raster_count"] == 0

    p_map = {p["primitive_id"]: p for p in rec["reconciled_primitives"]}
    assert p_map["r_stamp"]["reconciliation_role"] == RASTER_PRIMITIVE_PROMOTED_AUGMENTATION
    assert UNMATCHED_RASTER_PROMOTED in p_map["r_stamp"]["reason_codes"]


def test_authority_resolution_and_unregistered_selector():
    producer = SourceHybridMixedFormatRecoveryProducer.create()
    producer.register_page_primitives(
        document_id="doc-hybrid",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="1",
        vector_segments=[_seg("v1", 0, 0, 100, 0)],
        raster_segments=[_seg("r1", 0, 0.5, 100, 0.5)],
    )
    authority = producer.authority()

    sel = _make_selector()
    res = authority.resolve(sel)

    assert res.status == EvidenceResolutionStatus.CANDIDATE.value
    assert SOURCE_HYBRID_RECOVERY_RESOLVED in res.reason_codes
    assert res.detected_modality == MODALITY_MIXED_HYBRID
    assert res.vector_count == 1
    assert res.raster_count == 1
    assert res.reconciled_raster_count == 1
    assert res.promoted_raster_count == 0
    assert len(res.reconciled_primitives) == 2

    # Unregistered selector
    sel_unreg = _make_selector(page="99")
    res_unreg = authority.resolve(sel_unreg)
    assert res_unreg.status == EvidenceResolutionStatus.ABSTAINED.value
    assert SOURCE_HYBRID_RECOVERY_UNAVAILABLE in res_unreg.reason_codes
