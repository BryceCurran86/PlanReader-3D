"""Source-closed opening-area export from the final live production claim."""
from __future__ import annotations

import fitz

from pb_live_opening_source_closed_export import (
    build_live_opening_area_claim_source_traces,
    seal_live_opening_area_claim_run,
)
from pb_live_physical_net_wall_integration import (
    collect_live_physical_net_wall_claim,
)


def _opening_pdf() -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=760.0, height=650.0)
        for first, second in (
            ((20.0, 100.0), (100.0, 100.0)),
            ((145.0, 100.0), (220.0, 100.0)),
            ((20.0, 110.0), (100.0, 110.0)),
            ((145.0, 110.0), (220.0, 110.0)),
            ((100.0, 100.0), (100.0, 110.0)),
            ((145.0, 100.0), (145.0, 110.0)),
            ((100.0, 70.0), (145.0, 70.0)),
            ((100.0, 70.0), (100.0, 100.0)),
            ((145.0, 70.0), (145.0, 100.0)),
        ):
            page.draw_line(fitz.Point(*first), fitz.Point(*second), width=1.0)
        page.insert_text(fitz.Point(112.0, 65.0), "900")
        page.insert_text(fitz.Point(112.0, 106.0), "W1")

        headings = (
            "MARK",
            "ROWDTH-MM",
            "ROHT-MM",
            "ROUGH-OPENING-SILL-MM",
            "ROUGH-OPENING-HEAD-MM",
        )
        values = ("W1", "900", "2100", "900", "3000")
        xs = (50.0, 150.0, 250.0, 350.0, 550.0)
        for text, x in zip(headings, xs):
            page.insert_text(fitz.Point(x, 500.0), text)
        for text, x in zip(values, xs):
            page.insert_text(fitz.Point(x, 530.0), text)

        page.draw_line(fitz.Point(300.0, 250.0), fitz.Point(350.0, 250.0), width=1.0)
        page.draw_line(fitz.Point(300.0, 242.0), fitz.Point(300.0, 258.0), width=1.0)
        page.draw_line(fitz.Point(350.0, 242.0), fitz.Point(350.0, 258.0), width=1.0)
        page.insert_text(fitz.Point(298.0, 274.0), "0")
        page.insert_text(fitz.Point(346.0, 274.0), "1m")
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def test_final_live_claim_opening_area_seals_with_exact_physical_identity(tmp_path) -> None:
    path = tmp_path / "opening.pdf"
    path.write_bytes(_opening_pdf())

    claim = collect_live_physical_net_wall_claim(path, pages=(0,))

    assert len(claim.opening_quantity_evidence) == 1
    quantity = claim.opening_quantity_evidence[0]
    assert quantity.family == "opening_area"
    assert quantity.abstained is False
    assert len(quantity.input_entity_ids) == 1

    traces = build_live_opening_area_claim_source_traces(
        claim,
        workspace_id=17,
        project_id="project-opening-claim",
    )
    trace = traces[quantity.quantity_id]
    assert trace.canonical_entity_ids == quantity.input_entity_ids
    assert trace.source_sha256
    assert trace.revision_id == trace.current_revision_id
    assert set(quantity.evidence_ids).issubset(set(trace.evidence_ids))

    sealed = seal_live_opening_area_claim_run(
        claim,
        workspace_id=17,
        project_id="project-opening-claim",
    )
    assert len(sealed.quantities) == 1
    row = sealed.quantities[0]
    assert row.quantity_id == quantity.quantity_id
    assert row.family == "opening_area"
    assert row.object_identity_refs == quantity.input_entity_ids
    assert row.value == quantity.value
    assert row.lineage_ok is True


def test_final_live_claim_opening_area_sealing_is_deterministic(tmp_path) -> None:
    path = tmp_path / "opening.pdf"
    path.write_bytes(_opening_pdf())
    claim = collect_live_physical_net_wall_claim(path, pages=(0,))

    first = seal_live_opening_area_claim_run(
        claim,
        workspace_id=17,
        project_id="project-opening-claim",
    )
    second = seal_live_opening_area_claim_run(
        claim,
        workspace_id=17,
        project_id="project-opening-claim",
    )

    assert first.run_id == second.run_id
    assert first.fingerprint == second.fingerprint
