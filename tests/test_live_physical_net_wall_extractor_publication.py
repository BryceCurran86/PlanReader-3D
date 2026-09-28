from __future__ import annotations

from types import SimpleNamespace

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def _drawing_and_boq_pdf() -> bytes:
    doc = fitz.open()
    try:
        drawing = doc.new_page(width=760.0, height=650.0)
        drawing.insert_text(
            fitz.Point(40.0, 60.0),
            (
                "GROUND FLOOR PLAN SCALE 1:100 DRAWING TITLE ARCHITECTURAL PLAN "
                + "SOURCE DRAWING ANNOTATION " * 12
            ),
            fontsize=7.0,
        )
        boq = doc.new_page(width=760.0, height=650.0)
        boq.insert_text(
            fitz.Point(40.0, 60.0),
            (
                "BILL OF QUANTITIES RATE AMOUNT KSHS "
                + "MEASURED WORK ITEM DESCRIPTION RATE AMOUNT " * 10
            ),
            fontsize=7.0,
        )
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def test_extractor_scopes_live_physical_net_wall_to_drawing_pages_and_publishes_claim(
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "drawing-plus-boq.pdf"
    path.write_bytes(_drawing_and_boq_pdf())
    seen: dict[str, object] = {}

    def fake_physical_wall_claim(pdf_path, *, pages=None):
        seen["pdf_path"] = pdf_path
        seen["pages"] = list(pages or ())
        return SimpleNamespace(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=("test_physical_net_wall_resolved",),
            quantity_m2=42.5,
            source_pages=(1,),
            external_wall_ids=("whole-wall-1",),
            evidence_ids=("gross-1", "void-1", "role-1"),
            quantity_id="physical-net-wall-q1",
            confidence=1.0,
        )

    monkeypatch.setattr(
        "pb_live_physical_net_wall_integration.collect_live_physical_net_wall_claim",
        fake_physical_wall_claim,
    )
    monkeypatch.setattr(
        "pb_live_ceiling_lining_integration.collect_live_ceiling_lining_claims",
        lambda *args, **kwargs: SimpleNamespace(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=("test_no_ceiling",),
            claims=(),
        ),
    )

    extractor = GenericPlanReaderExtractor()
    predictions = extractor.extract_from_pdf(
        path,
        collect_item35_shadow=False,
    )

    assert seen["pages"] == [0]
    wall = next(pred for pred in predictions if pred.tag == "perimeter_walling")
    assert wall.quantity == 42.5
    assert wall.unit == "SM"
    assert wall.confidence == 1.0
    assert wall.source_page == 1
    assert wall.dimensions is None
    assert wall.metadata["derivation"] == "source_owned_physical_external_net_wall"
    assert wall.metadata["commercial_projection_allowed"] is True
    assert wall.metadata["raw_evidence_ref"] == "physical-net-wall-q1"
    assert extractor.physical_net_wall_live["status"] == "corroborated"
    assert extractor.extraction_status["physical_net_wall_live"] == "corroborated"
