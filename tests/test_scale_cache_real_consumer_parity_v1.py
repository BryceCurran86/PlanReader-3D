"""Order 8 real consumer parity tests: pb_scale_block_bar_shadow + pb_opening_schedule_v171 + SourceHashEvidenceCache."""

from __future__ import annotations

from pathlib import Path
import tracemalloc

import fitz

from pb_opening_schedule_v171 import parse_schedule_page
from pb_scale_block_bar_shadow import detect_block_scale_bars
from pb_source_hash_evidence_cache_shadow import (
    IndexedSpatialItem,
    SourceEvidenceCacheKey,
    SourceHashEvidenceCache,
    SpatialApertureEvidenceIndex,
    canonical_sha256,
)
from pb_source_scale_lineage_audit_shadow import (
    DimensionChainScaleWitness,
    GraphicScaleBarWitness,
    MM_PER_PT_AT_1_TO_1,
    PrintedScaleNoteWitness,
    ScaleLineageRef,
    audit_viewport_scale_lineage_shadow,
)


def _make_real_schedule_pdf(revision_tag: str, *, d01_width: int = 920) -> bytes:
    """Single-row standard door schedule matching default pb_opening_schedule_v171 on main."""
    doc = fitz.open()
    page = doc.new_page(width=520, height=360)
    items = [
        (30.0, 35.0, f"DOOR SCHEDULE {revision_tag}"),
        (30.0, 70.0, "DOOR"),
        (130.0, 70.0, "WIDTH"),
        (220.0, 70.0, "HEIGHT"),
        (30.0, 100.0, "D01"),
        (130.0, 100.0, str(d01_width)),
        (220.0, 100.0, "2040"),
        (30.0, 125.0, "D02"),
        (130.0, 125.0, "820"),
        (220.0, 125.0, "2040"),
    ]
    for x, y, text in items:
        page.insert_text((x, y), text, fontsize=9)
    raw = doc.tobytes()
    doc.close()
    return raw


def test_real_consumer_scale_block_bar_feeds_scale_lineage_audit_with_exact_parity() -> None:
    """Real pb_scale_block_bar_shadow.detect_block_scale_bars -> audit_viewport_scale_lineage_shadow."""
    # Construct a 1:100 block scale bar: 0, 1, 2, 3, 4, 5m
    # At 1:100, 1000 mm = 1000 / (100 * 25.4/72) = 28.34645669 pts
    step_pt = 1000.0 / (100.0 * MM_PER_PT_AT_1_TO_1)
    x0 = 100.0
    words = []
    segments = []
    for idx in range(6):
        cx = x0 + idx * step_pt
        label = f"{idx}m" if idx == 5 else str(idx)
        words.append({"id": f"w_{idx}", "text": label, "bbox": (cx - 4.0, 200.0, cx + 4.0, 210.0)})
        # Vertical block edge right above each label (height 15 pt = 1.5x numeral height)
        segments.append({"id": f"e_{idx}", "x1": cx, "y1": 180.0, "x2": cx, "y2": 195.0})
    words.append({"id": "w_ratio", "text": "1:100", "bbox": (400.0, 200.0, 430.0, 210.0)})

    block_report = detect_block_scale_bars(segments, words)
    assert block_report.scale_authority_granted is False
    assert len(block_report.candidates) == 1
    cand = block_report.candidates[0]

    lin = ScaleLineageRef("doc_arch", "rev_01", "a" * 64, "page_01", "vp_plan_100")
    bar_witness = GraphicScaleBarWitness(
        bar_id="block_bar_0",
        lineage=lin,
        bar_kind="block_bar",
        span_pts=cand.span_pt,
        physical_span_mm=cand.physical_span_mm,
        residual_pt=max(cand.label_residual_pt, cand.edge_residual_pt),
    )
    chains = (
        DimensionChainScaleWitness("ch_x", lin, "x", span_pts=4.0 * step_pt, figured_mm=4000.0),
        DimensionChainScaleWitness("ch_y", lin, "y", span_pts=3.0 * step_pt, figured_mm=3000.0),
    )
    note_ok = PrintedScaleNoteWitness("n_100", lin, "SCALE 1:100")
    audit = audit_viewport_scale_lineage_shadow(
        lin, dimension_chains=chains, scale_bars=(bar_witness,), printed_notes=(note_ok,)
    )
    assert audit.calibrated is True
    assert audit.ratio_corroborated is True
    assert audit.equivalent_ratio is not None and abs(audit.equivalent_ratio - 100.0) < 0.05
    assert audit.scale_authority_granted is False
    assert audit.commercial_authority_granted is False

    # Negative: same real block bar (1:100) vs wrong printed ratio (1:50) -> fail closed!
    audit_mismatch = audit_viewport_scale_lineage_shadow(
        lin,
        scale_bars=(bar_witness,),
        printed_notes=(PrintedScaleNoteWitness("n_50", lin, "SCALE 1:50"),),
    )
    assert audit_mismatch.abstained is True
    assert "printed_ratio_disagrees_with_geometric_scale" in audit_mismatch.blocking_reasons


def test_real_schedule_consumer_cache_parity_cold_warm_time_memory_and_invalidation(tmp_path: Path) -> None:
    """Real pb_opening_schedule_v171.parse_schedule_page wrapped in SourceHashEvidenceCache."""
    pdf_a = _make_real_schedule_pdf("REV_A", d01_width=920)
    pdf_b = _make_real_schedule_pdf("REV_B", d01_width=970)

    def _run_real_schedule_consumer(raw_bytes: bytes) -> dict[str, object]:
        doc = fitz.open(stream=raw_bytes, filetype="pdf")
        try:
            entries = parse_schedule_page(doc[0], page_no=1, two_level_header=False)
            rows = [
                {
                    "type_mark": e.type_mark,
                    "width_mm": e.width_mm,
                    "height_mm": e.height_mm,
                    "dimension_basis": e.dimension_basis,
                }
                for e in entries
            ]
            # Verify spatial index exact parity over real extracted word boxes
            words = doc[0].get_text("words")
            items = [IndexedSpatialItem(f"w_{i}", (w[0], w[1], w[2], w[3])) for i, w in enumerate(words)]
            idx = SpatialApertureEvidenceIndex(items, cell_size_pts=40.0)
            q = (20.0, 50.0, 260.0, 150.0)
            assert idx.query_bbox(q) == idx.brute_force_query_bbox(q)
            return {
                "entry_count": len(rows),
                "entries": rows,
                "indexed_hits": len(idx.query_bbox(q)),
                "commercial_authority_granted": False,
            }
        finally:
            doc.close()

    uncached_direct = _run_real_schedule_consumer(pdf_a)
    assert uncached_direct["entry_count"] == 2

    cache = SourceHashEvidenceCache(cache_dir=tmp_path / "real_sched_cache")
    key_a = SourceEvidenceCacheKey.from_raw_bytes(
        pdf_a,
        document_id="doc_sched",
        revision_id="rev_a",
        page_index=0,
        viewport_id="vp_sched",
        stage_name="parse_schedule_page",
        producer_schema_version="1.0.0",
        options={"two_level_header": False},
    )

    tracemalloc.start()
    val_cold, rec_cold = cache.get_or_compute(key_a, lambda: _run_real_schedule_consumer(pdf_a))
    _, peak_cold_bytes = tracemalloc.get_traced_memory()
    tracemalloc.reset_peak()
    val_warm, rec_warm = cache.get_or_compute(key_a, lambda: _run_real_schedule_consumer(pdf_a))
    _, peak_warm_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert rec_cold.cache_hit is False
    assert rec_warm.cache_hit is True
    assert val_cold == uncached_direct
    assert val_warm == uncached_direct
    assert canonical_sha256(val_warm) == canonical_sha256(uncached_direct)
    assert rec_warm.value_sha256 == rec_cold.value_sha256
    assert rec_warm.elapsed_ms < rec_cold.elapsed_ms
    assert peak_cold_bytes > 0 and peak_warm_bytes >= 0
    assert val_warm["commercial_authority_granted"] is False

    # Mutating PDF bytes (d01_width 920 -> 970) produces a new source_sha256 -> guaranteed cache MISS!
    key_b = SourceEvidenceCacheKey.from_raw_bytes(
        pdf_b,
        document_id="doc_sched",
        revision_id="rev_a",
        page_index=0,
        viewport_id="vp_sched",
        stage_name="parse_schedule_page",
        producer_schema_version="1.0.0",
        options={"two_level_header": False},
    )
    assert key_b.source_sha256 != key_a.source_sha256
    val_b, rec_b = cache.get_or_compute(key_b, lambda: _run_real_schedule_consumer(pdf_b))
    assert rec_b.cache_hit is False
    assert val_b["entries"][0]["width_mm"] == 970
    assert rec_b.value_sha256 != rec_cold.value_sha256
