"""Unit tests for Item 28: source-hash/revision-safe evidence cache, spatial index & parity."""

from __future__ import annotations

import json
from pathlib import Path
import random

import fitz
import pytest

from pb_source_hash_evidence_cache_shadow import (
    CacheIntegrityError,
    IndexedSpatialItem,
    SourceEvidenceCacheKey,
    SourceHashEvidenceCache,
    SpatialApertureEvidenceIndex,
    canonical_sha256,
)
from tools.audit_no_job_specific_shared_rules import audit_shared_source


def _make_pdf_bytes(label: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), f"DOOR SCHEDULE {label}", fontsize=11)
    page.insert_text((72, 130), "D01 920 x 2040", fontsize=10)
    page.draw_rect(fitz.Rect(60, 80, 300, 160), color=(0, 0, 0), width=1.0)
    data = doc.tobytes()
    doc.close()
    return data


def _extract_native_page_summary(pdf_bytes: bytes, page_index: int) -> dict[str, object]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = doc[page_index]
        words = sorted(
            (round(w[0], 2), round(w[1], 2), round(w[2], 2), round(w[3], 2), str(w[4]))
            for w in page.get_text("words")
        )
        drawings = page.get_drawings()
        return {
            "word_count": len(words),
            "words": [list(w) for w in words],
            "drawing_count": len(drawings),
        }
    finally:
        doc.close()


def test_source_hash_cache_exact_parity_invalidation_and_anti_poisoning(tmp_path: Path) -> None:
    pdf_v1 = _make_pdf_bytes("REV_A")
    pdf_v2 = _make_pdf_bytes("REV_B")

    cache = SourceHashEvidenceCache(cache_dir=tmp_path / "ev_cache")
    calls = {"count": 0}

    def produce(data: bytes) -> dict[str, object]:
        calls["count"] += 1
        return _extract_native_page_summary(data, 0)

    key_v1 = SourceEvidenceCacheKey.from_raw_bytes(
        pdf_v1,
        document_id="doc_sched",
        revision_id="rev_a",
        page_index=0,
        viewport_id="vp_main",
        stage_name="native_pdf_extract",
        producer_schema_version="1.0.0",
        options={"source_native_finish_text_shadow": True},
    )

    # First run: cache miss
    val1, rec1 = cache.get_or_compute(key_v1, lambda: produce(pdf_v1))
    assert rec1.cache_hit is False
    assert calls["count"] == 1

    # Downstream mutation MUST NOT poison subsequent cache hits
    val1["words"].append([0, 0, 1, 1, "MUTATED"])
    val1["word_count"] = 9999

    # Second run (same source hash/revision/options): exact parity cache hit!
    val2, rec2 = cache.get_or_compute(key_v1, lambda: produce(pdf_v1))
    assert rec2.cache_hit is True
    assert calls["count"] == 1
    assert rec2.value_sha256 == rec1.value_sha256
    assert val2["word_count"] != 9999
    assert canonical_sha256(val2) == canonical_sha256(_extract_native_page_summary(pdf_v1, 0))

    # Reload from fresh on-disk cache instance -> still hits & exact parity
    cache_reloaded = SourceHashEvidenceCache(cache_dir=tmp_path / "ev_cache")
    val_disk, rec_disk = cache_reloaded.get_or_compute(key_v1, lambda: produce(pdf_v1))
    assert rec_disk.cache_hit is True
    assert rec_disk.value_sha256 == rec1.value_sha256
    assert val_disk == val2

    # Invalidation matrix: changing ANY single dimension MUST miss!
    key_diff_bytes = SourceEvidenceCacheKey.from_raw_bytes(
        pdf_v2, document_id="doc_sched", revision_id="rev_a", page_index=0,
        viewport_id="vp_main", stage_name="native_pdf_extract", producer_schema_version="1.0.0",
        options={"source_native_finish_text_shadow": True},
    )
    key_diff_rev = SourceEvidenceCacheKey.from_raw_bytes(
        pdf_v1, document_id="doc_sched", revision_id="rev_b", page_index=0,
        viewport_id="vp_main", stage_name="native_pdf_extract", producer_schema_version="1.0.0",
        options={"source_native_finish_text_shadow": True},
    )
    key_diff_vp = SourceEvidenceCacheKey.from_raw_bytes(
        pdf_v1, document_id="doc_sched", revision_id="rev_a", page_index=0,
        viewport_id="vp_inset", stage_name="native_pdf_extract", producer_schema_version="1.0.0",
        options={"source_native_finish_text_shadow": True},
    )
    key_diff_opt = SourceEvidenceCacheKey.from_raw_bytes(
        pdf_v1, document_id="doc_sched", revision_id="rev_a", page_index=0,
        viewport_id="vp_main", stage_name="native_pdf_extract", producer_schema_version="1.0.0",
        options={"source_native_finish_text_shadow": False},
    )
    key_diff_ver = SourceEvidenceCacheKey.from_raw_bytes(
        pdf_v1, document_id="doc_sched", revision_id="rev_a", page_index=0,
        viewport_id="vp_main", stage_name="native_pdf_extract", producer_schema_version="2.0.0",
        options={"source_native_finish_text_shadow": True},
    )
    for k, src in (
        (key_diff_bytes, pdf_v2),
        (key_diff_rev, pdf_v1),
        (key_diff_vp, pdf_v1),
        (key_diff_opt, pdf_v1),
        (key_diff_ver, pdf_v1),
    ):
        _, r = cache.get_or_compute(k, lambda s=src: produce(s))
        assert r.cache_hit is False
    assert calls["count"] == 6

    # On-disk payload tampering MUST fail closed with CacheIntegrityError
    entry_file = (tmp_path / "ev_cache") / f"{key_v1.key_digest_sha256()}.json"
    tampered = json.loads(entry_file.read_text(encoding="utf-8"))
    tampered["payload"]["word_count"] = -1
    entry_file.write_text(json.dumps(tampered), encoding="utf-8")

    cache_tampered = SourceHashEvidenceCache(cache_dir=tmp_path / "ev_cache")
    with pytest.raises(CacheIntegrityError):
        cache_tampered.get_or_compute(key_v1, lambda: produce(pdf_v1))


def test_spatial_aperture_index_exact_parity_with_brute_force() -> None:
    rng = random.Random(20261125)
    items = []
    for i in range(600):
        x0 = rng.uniform(0.0, 1200.0)
        y0 = rng.uniform(0.0, 840.0)
        w = rng.uniform(2.0, 90.0)
        h = rng.uniform(2.0, 90.0)
        items.append(IndexedSpatialItem(f"seg_{i:04d}", (x0, y0, x0 + w, y0 + h)))

    index = SpatialApertureEvidenceIndex(items, cell_size_pts=40.0)
    for _ in range(100):
        qx0 = rng.uniform(-10.0, 1180.0)
        qy0 = rng.uniform(-10.0, 820.0)
        qbox = (qx0, qy0, qx0 + rng.uniform(5.0, 120.0), qy0 + rng.uniform(5.0, 120.0))
        pad = rng.choice((0.0, 4.0, 12.5))
        assert index.query_bbox(qbox, pad_pts=pad) == index.brute_force_query_bbox(qbox, pad_pts=pad)


def test_shared_source_audit_is_clean() -> None:
    p = Path(__file__).resolve().parent.parent / "pb_source_hash_evidence_cache_shadow.py"
    assert audit_shared_source(p.read_text(encoding="utf-8"), filename=p.name) == ()
