"""Exact original ceiling source-page selection must fail closed before ingest.

These are generated, source-neutral PDF regressions, not original-plan proof.
"""
from __future__ import annotations

import fitz
import pytest

import pb_live_ceiling_lining_integration as ceiling


def _generated_two_page_pdf(tmp_path):
    doc = fitz.open()
    try:
        doc.new_page(width=300, height=200)
        doc.new_page(width=300, height=200)
        path = tmp_path / "synthetic-ceiling-pages.pdf"
        path.write_bytes(doc.tobytes(garbage=4, deflate=True))
        return path
    finally:
        doc.close()


def test_explicit_valid_ceiling_source_page_universe_is_sorted_and_idempotent():
    selected = [1, 0, 1]
    original = selected[:]
    assert ceiling._selected_page_indices(2, selected) == (0, 1)
    assert ceiling._selected_page_indices(2, selected) == (0, 1)
    assert selected == original
    assert ceiling._selected_page_indices(2, range(2)) == (0, 1)
    assert ceiling._selected_page_indices(2, ()) == ()
    assert ceiling._selected_page_indices(2, None) == (0, 1)


@pytest.mark.parametrize(
    "pages",
    [
        (0, True),
        (0, False),
        (0, 0.0),
        (0, 1.0),
        (0, "1"),
        (0, b"1"),
        (0, -1),
        (0, 2),
        (0, 10**1000),
        (0, float("nan")),
        (0, object()),
        ("0", "1"),
        "01",
        b"01",
        {0: 1},
        0,
        1.0,
    ],
)
def test_malformed_ceiling_source_page_universe_is_not_silently_repaired(pages):
    with pytest.raises(ValueError, match="original ceiling page selection"):
        ceiling._selected_page_indices(2, pages)


@pytest.mark.parametrize(
    "bad",
    [True, False, 0.0, 1.0, "1", b"1", -1, 2, 10**1000, float("nan"), object()],
)
@pytest.mark.parametrize("which", ["pages", "topology_pages"])
def test_invalid_source_or_topology_sibling_aborts_before_pdf_ingestion(
    tmp_path, monkeypatch, bad, which
):
    path = _generated_two_page_pdf(tmp_path)
    ingestions = []

    def forbid_ingest(*args, **kwargs):
        ingestions.append(kwargs)
        raise AssertionError("invalid page selection reached original PDF ingestion")

    monkeypatch.setattr(
        ceiling.SourceVisibilityProducer, "ingest_native_pdf_bytes", forbid_ingest
    )
    kwargs = (
        {"pages": (0, bad), "topology_pages": (0,)}
        if which == "pages"
        else {"pages": (0, 1), "topology_pages": (0, bad)}
    )
    with pytest.raises(ValueError, match="original ceiling page selection"):
        ceiling.collect_live_ceiling_lining_claims(path, **kwargs)
    assert ingestions == []


def test_valid_ceiling_page_and_topology_split_preserves_exact_source_scope(
    tmp_path, monkeypatch
):
    path = _generated_two_page_pdf(tmp_path)
    ingested = []
    scanned = []
    original_ingest = ceiling.SourceVisibilityProducer.ingest_native_pdf_bytes

    def capture_ingest(self, *args, **kwargs):
        ingested.append(tuple(kwargs.get("page_ids") or ()))
        return original_ingest(self, *args, **kwargs)

    def capture_viewports(page, *, page_number):
        scanned.append(page_number)
        return ()

    monkeypatch.setattr(
        ceiling.SourceVisibilityProducer, "ingest_native_pdf_bytes", capture_ingest
    )
    monkeypatch.setattr(
        ceiling, "authoritative_floor_plan_viewports", capture_viewports
    )
    selected = [1, 0, 1]
    topology = [1, 1]
    result = ceiling.collect_live_ceiling_lining_claims(
        path, pages=selected, topology_pages=topology
    )
    assert ingested == [("1", "2")]
    assert scanned == [2]
    assert result.claims == ()
    assert result.canonical_ceilings == ()
    assert selected == [1, 0, 1]
    assert topology == [1, 1]


def test_ceiling_topology_subset_conflict_aborts_before_ingestion(
    tmp_path, monkeypatch
):
    path = _generated_two_page_pdf(tmp_path)
    ingestions = []

    def forbid_ingest(*args, **kwargs):
        ingestions.append(kwargs)
        raise AssertionError("invalid topology subset reached original ingestion")

    monkeypatch.setattr(
        ceiling.SourceVisibilityProducer, "ingest_native_pdf_bytes", forbid_ingest
    )
    with pytest.raises(ValueError, match="topology_pages must be a subset"):
        ceiling.collect_live_ceiling_lining_claims(
            path, pages=(0,), topology_pages=(1,)
        )
    assert ingestions == []
