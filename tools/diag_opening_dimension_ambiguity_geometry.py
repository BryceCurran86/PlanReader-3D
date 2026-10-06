from __future__ import annotations

import json
import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_label_dimension_authority import (
    _gap_span_for_opening,
    _label_matches_gap,
    _trusted_text_lines,
)
from pb_opening_label_semantic_authority import _trusted_native_lines
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def pdf() -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=320.0, height=220.0)
        for first, second in (
            ((20.0, 100.0), (100.0, 100.0)),
            ((140.0, 100.0), (220.0, 100.0)),
            ((20.0, 110.0), (100.0, 110.0)),
            ((140.0, 110.0), (220.0, 110.0)),
            ((100.0, 100.0), (100.0, 110.0)),
            ((140.0, 100.0), (140.0, 110.0)),
        ):
            page.draw_line(fitz.Point(*first), fitz.Point(*second), width=1.0)
        page.insert_text(fitz.Point(88.0, 121.0), "900 - 1200 asw", fontsize=7.0)
        page.insert_text(fitz.Point(88.0, 130.0), "1000 - 1200 asw", fontsize=7.0)
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def main() -> None:
    source = SourceVisibilityProducer(
        producer_method="diag-opening-ambiguity",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="diag-opening-ambiguity",
        source_bytes=pdf(),
        source_locator="memory://diag-opening-ambiguity.pdf",
    )
    physical = source.physical_opening_authority()
    found = {}
    for observation_id in published.visible_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = physical.prove_existence(selector)
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.proposition == PHYSICAL_OPENING_EXISTS
            and result.existence_record is not None
        ):
            found[result.existence_record.record_id] = result.existence_record
    opening = next(iter(found.values()))
    gap = _gap_span_for_opening(source, opening)
    lines = _trusted_text_lines(source, opening)
    native_lines = _trusted_native_lines(source, opening)
    print(json.dumps({
        "opening_id": opening.record_id,
        "gap": None if gap is None else {
            "axis": gap.axis,
            "normal": gap.normal,
            "along_min": gap.along_min,
            "along_max": gap.along_max,
            "cross_center": gap.cross_center,
            "cross_spread": gap.cross_spread,
        },
        "native_lines": [
            {
                "block_no": block_no,
                "line_no": line_no,
                "text": line.text,
                "bbox": line.bbox,
                "observation_ids": line.observation_ids,
            }
            for block_no, line_no, line in native_lines
        ],
        "lines": [
            {
                "text": line.text,
                "bbox": line.bbox,
                "match": False if gap is None else _label_matches_gap(line, gap),
                "center": [
                    (line.bbox[0] + line.bbox[2]) / 2.0,
                    (line.bbox[1] + line.bbox[3]) / 2.0,
                ],
                "glyph_height_proxy": min(
                    abs(line.bbox[2] - line.bbox[0]),
                    abs(line.bbox[3] - line.bbox[1]),
                ),
            }
            for line in lines
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
