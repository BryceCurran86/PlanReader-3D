from __future__ import annotations

from types import SimpleNamespace

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def _non_drawing_pdf() -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=400.0, height=250.0)
        page.insert_text(
            fitz.Point(40.0, 60.0),
            "BILL OF QUANTITIES RATE AMOUNT KSHS",
            fontsize=8.0,
        )
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def test_reused_extractor_clears_all_live_canonical_object_state(
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "non-drawing.pdf"
    path.write_bytes(_non_drawing_pdf())

    monkeypatch.setattr(
        "pb_live_ceiling_lining_integration.collect_live_ceiling_lining_claims",
        lambda *args, **kwargs: SimpleNamespace(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=("test_no_ceiling",),
            claims=(),
            canonical_ceilings=(),
        ),
    )

    extractor = GenericPlanReaderExtractor()
    extractor.canonical_walls_live = {"status": "corroborated", "walls": [{"id": "stale-wall"}]}
    extractor.canonical_openings_live = {"status": "corroborated", "openings": [{"id": "stale-opening"}]}
    extractor.canonical_doors_live = {"status": "corroborated", "doors": [{"id": "stale-door"}]}
    extractor.canonical_windows_live = {"status": "corroborated", "windows": [{"id": "stale-window"}]}
    extractor.canonical_rooms_live = {"status": "corroborated", "rooms": [{"id": "stale-room"}]}
    extractor.canonical_slabs_live = {"status": "corroborated", "slabs": [{"id": "stale-slab"}]}
    extractor.canonical_ceilings_live = {"status": "corroborated", "ceilings": [{"id": "stale-ceiling"}]}
    extractor.canonical_roofs_live = {"status": "corroborated", "roofs": [{"id": "stale-roof"}]}
    extractor.canonical_structural_members_live = {
        "status": "corroborated",
        "members": [{"id": "stale-structural-member"}],
    }

    extractor.extract_from_pdf(
        path,
        collect_item35_shadow=False,
    )

    assert extractor.canonical_walls_live["walls"] == []
    assert extractor.canonical_openings_live["openings"] == []
    assert extractor.canonical_doors_live["doors"] == []
    assert extractor.canonical_windows_live["windows"] == []
    assert extractor.canonical_rooms_live["rooms"] == []
    assert extractor.canonical_slabs_live["slabs"] == []
    assert extractor.canonical_ceilings_live["ceilings"] == []
    assert extractor.canonical_roofs_live["roofs"] == []
    assert extractor.canonical_structural_members_live["members"] == []

    assert extractor.canonical_walls_live["status"] == "abstained"
    assert extractor.canonical_openings_live["status"] == "abstained"
    assert extractor.canonical_doors_live["status"] == "abstained"
    assert extractor.canonical_windows_live["status"] == "abstained"
    assert extractor.canonical_rooms_live["status"] == "abstained"
    assert extractor.canonical_slabs_live["status"] == "abstained"
    assert extractor.canonical_ceilings_live["status"] == "abstained"
    assert extractor.canonical_roofs_live["status"] == "abstained"
    assert extractor.canonical_structural_members_live["status"] == "abstained"
