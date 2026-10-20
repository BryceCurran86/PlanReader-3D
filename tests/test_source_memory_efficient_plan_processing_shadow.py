"""Tests for producer-owned memory-efficient plan processing shadow authority (Item 24)."""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_memory_efficient_plan_processing_shadow import (
    PAGE_MEMORY_BUDGET_EXCEEDED,
    PAGE_PRIMITIVE_CAP_ENFORCED,
    PAGE_STREAMING_COMPLETED,
    PLAN_MEMORY_BUDGET_EXCEEDED,
    SOURCE_MEMORY_EFFICIENT_PLAN_CANDIDATE,
    SOURCE_MEMORY_EFFICIENT_PLAN_RESOLVED,
    SOURCE_MEMORY_EFFICIENT_PLAN_UNAVAILABLE,
    SPATIAL_CHUNK_INDEX_APPLIED,
    SpatialChunkGrid,
    SourceMemoryEfficientPlanProcessingAuthority,
    SourceMemoryEfficientPlanProcessingProducer,
    SourceMemoryEfficientPlanSelector,
    SourcePageMemoryReceiptRecord,
)


def _seg(ident, x1=0.0, y1=0.0, x2=10.0, y2=10.0):
    return {"id": ident, "x1": float(x1), "y1": float(y1), "x2": float(x2), "y2": float(y2)}


def _make_selector(
    *,
    doc="doc-plan-set",
    rev="rev-01",
    sha="a" * 64,
    snap="snap-01",
    page_ids=(),
    max_page_mb=64.0,
    max_plan_mb=256.0,
) -> SourceMemoryEfficientPlanSelector:
    return SourceMemoryEfficientPlanSelector(
        document_id=doc,
        revision_id=rev,
        source_sha256=sha,
        snapshot_id=snap,
        page_ids=page_ids,
        max_page_memory_mb=max_page_mb,
        max_plan_memory_mb=max_plan_mb,
    )


def test_sealing_raises_permission_error():
    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceMemoryEfficientPlanProcessingProducer(object())

    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceMemoryEfficientPlanProcessingAuthority(object(), {})

    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourcePageMemoryReceiptRecord(
            page_id="1",
            primitive_count=100,
            estimated_memory_mb=0.15,
            quarantined=False,
            spatial_chunks_count=4,
            reason_codes=(),
        )


def test_multi_page_plan_streaming_success():
    producer = SourceMemoryEfficientPlanProcessingProducer.create()
    for p in range(1, 4):
        segs = [_seg(f"p{p}_s{i}", x1=i, y1=i, x2=i + 5, y2=i + 5) for i in range(100)]
        producer.register_page(
            document_id="doc-plan-set",
            revision_id="rev-01",
            source_sha256="a" * 64,
            snapshot_id="snap-01",
            page_id=str(p),
            segments=segs,
            page_width=500.0,
            page_height=500.0,
        )

    authority = producer.authority()
    sel = _make_selector()
    res = authority.resolve(sel)

    assert res.status == EvidenceResolutionStatus.CORROBORATED.value
    assert SOURCE_MEMORY_EFFICIENT_PLAN_RESOLVED in res.reason_codes
    assert res.total_pages == 3
    assert res.processed_pages == 3
    assert res.quarantined_pages == 0
    assert len(res.page_receipts) == 3
    for r in res.page_receipts:
        assert r.quarantined is False
        assert PAGE_STREAMING_COMPLETED in r.reason_codes
        assert r.status == EvidenceResolutionStatus.CANDIDATE.value
        assert r.commercial_projection_allowed is False
        assert r.takeoff_eligible is False


def test_page_memory_budget_exceeded_quarantines_safely():
    producer = SourceMemoryEfficientPlanProcessingProducer.create()

    # Normal Page 1: 100 segments (~0.15 MB)
    p1_segs = [_seg(f"p1_s{i}") for i in range(100)]
    producer.register_page(
        document_id="doc-plan-set",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="1",
        segments=p1_segs,
        page_width=500.0,
        page_height=500.0,
    )

    # Huge Page 2: 50,000 segments (~73 MB)
    p2_segs = [_seg(f"p2_s{i}") for i in range(50000)]
    producer.register_page(
        document_id="doc-plan-set",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="2",
        segments=p2_segs,
        page_width=500.0,
        page_height=500.0,
    )

    # Normal Page 3: 100 segments (~0.15 MB)
    p3_segs = [_seg(f"p3_s{i}") for i in range(100)]
    producer.register_page(
        document_id="doc-plan-set",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="3",
        segments=p3_segs,
        page_width=500.0,
        page_height=500.0,
    )

    authority = producer.authority()
    # Max page memory set to 50 MB (Page 2 exceeds it)
    sel = _make_selector(max_page_mb=50.0)
    res = authority.resolve(sel)

    assert res.status == EvidenceResolutionStatus.CANDIDATE.value
    assert SOURCE_MEMORY_EFFICIENT_PLAN_CANDIDATE in res.reason_codes
    assert res.total_pages == 3
    assert res.processed_pages == 2
    assert res.quarantined_pages == 1

    # Page 1 & 3 processed, Page 2 quarantined safely
    assert res.page_receipts[0].quarantined is False
    assert res.page_receipts[1].quarantined is True
    assert PAGE_MEMORY_BUDGET_EXCEEDED in res.page_receipts[1].reason_codes
    assert PAGE_PRIMITIVE_CAP_ENFORCED in res.page_receipts[1].reason_codes
    assert res.page_receipts[2].quarantined is False


def test_dense_page_spatial_chunk_grid_indexing():
    producer = SourceMemoryEfficientPlanProcessingProducer.create()
    # 2,500 segments: triggers spatial chunk index
    segs = [_seg(f"s_{i}", x1=(i % 50) * 10, y1=(i // 50) * 10, x2=(i % 50) * 10 + 5, y2=(i // 50) * 10 + 5) for i in range(2500)]
    producer.register_page(
        document_id="doc-plan-set",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="1",
        segments=segs,
        page_width=500.0,
        page_height=500.0,
    )
    authority = producer.authority()
    res = authority.resolve(_make_selector())

    assert res.status == EvidenceResolutionStatus.CORROBORATED.value
    rec = res.page_receipts[0]
    assert rec.primitive_count == 2500
    assert SPATIAL_CHUNK_INDEX_APPLIED in rec.reason_codes
    assert rec.spatial_chunks_count > 0


def test_plan_memory_budget_exceeded_flag():
    producer = SourceMemoryEfficientPlanProcessingProducer.create()
    # 5 pages each with 5,000 segments (~7.3 MB each = ~36.5 MB total)
    for p in range(1, 6):
        segs = [_seg(f"p{p}_s{i}") for i in range(5000)]
        producer.register_page(
            document_id="doc-plan-set",
            revision_id="rev-01",
            source_sha256="a" * 64,
            snapshot_id="snap-01",
            page_id=str(p),
            segments=segs,
            page_width=500.0,
            page_height=500.0,
        )
    authority = producer.authority()
    # Set max plan memory to 20 MB (total 36.5 MB exceeds it)
    sel = _make_selector(max_page_mb=64.0, max_plan_mb=20.0)
    res = authority.resolve(sel)

    assert PLAN_MEMORY_BUDGET_EXCEEDED in res.reason_codes


def test_unregistered_plan_returns_unavailable():
    producer = SourceMemoryEfficientPlanProcessingProducer.create()
    authority = producer.authority()
    res = authority.resolve(_make_selector(doc="NON-EXISTENT"))
    assert res.status == EvidenceResolutionStatus.ABSTAINED.value
    assert SOURCE_MEMORY_EFFICIENT_PLAN_UNAVAILABLE in res.reason_codes
