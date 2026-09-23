from __future__ import annotations

import fitz

from pb_live_wall_opening_authority_shadow import (
    PHYSICAL_OPENING_VOID_NOT_COMPOSED,
    collect_live_wall_opening_authority_shadow,
)
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def _host_fixture_pdf() -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=320.0, height=240.0)
        shape = page.new_shape()
        for start, end in (
            ((20.0, 80.0), (120.0, 80.0)),
            ((160.0, 80.0), (280.0, 80.0)),
            ((20.0, 100.0), (120.0, 100.0)),
            ((160.0, 100.0), (280.0, 100.0)),
            ((120.0, 80.0), (120.0, 100.0)),
            ((160.0, 80.0), (160.0, 100.0)),
        ):
            shape.draw_line(fitz.Point(*start), fitz.Point(*end))
        shape.finish(width=1.0)
        shape.commit()
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def test_authority_shadow_reports_first_uncomposed_causal_gate(tmp_path) -> None:
    path = tmp_path / "wall-opening-shadow.pdf"
    path.write_bytes(_host_fixture_pdf())

    shadow = collect_live_wall_opening_authority_shadow(
        path,
        document_id="wall-opening-shadow",
        page_indexes=(0,),
    )

    assert shadow["status"] == "corroborated"
    assert shadow["page_ids"] == ("1",)
    assert shadow["stages"]
    required = {
        "FILE",
        "CLASS/FUNCTION",
        "STATUS",
        "REASON_CODES",
        "RECORD PRESENT",
        "RECORD ID",
        "INPUT LINEAGE",
        "OUTPUT LINEAGE",
    }
    assert all(required <= set(stage) for stage in shadow["stages"])

    failure = shadow["first_causal_failure"]
    assert failure is not None
    assert failure["FILE"] == "pb_physical_opening_void_authority.py"
    assert failure["CLASS/FUNCTION"] == "PhysicalOpeningVoidProducer.publish"
    assert failure["STATUS"] == "not_composed"
    assert failure["REASON_CODES"] == (PHYSICAL_OPENING_VOID_NOT_COMPOSED,)
    assert failure["RECORD PRESENT"] is False


def test_extractor_shadow_never_mutates_live_predictions(tmp_path) -> None:
    path = tmp_path / "extractor-shadow-parity.pdf"
    path.write_bytes(_host_fixture_pdf())

    without_shadow = GenericPlanReaderExtractor()
    baseline = without_shadow.extract_from_pdf(
        path,
        pages=(0,),
        collect_item35_shadow=False,
        collect_wall_opening_authority_shadow=False,
    )

    with_shadow = GenericPlanReaderExtractor()
    candidate = with_shadow.extract_from_pdf(
        path,
        pages=(0,),
        collect_item35_shadow=False,
        collect_wall_opening_authority_shadow=True,
    )

    assert [prediction.to_dict() for prediction in candidate] == [
        prediction.to_dict() for prediction in baseline
    ]
    assert with_shadow.wall_opening_authority_shadow["status"] == "corroborated"
    assert (
        with_shadow.wall_opening_authority_shadow["first_causal_failure"]["FILE"]
        == "pb_physical_opening_void_authority.py"
    )
    assert (
        with_shadow.extraction_status["wall_opening_authority_shadow"]
        == "corroborated"
    )
