"""One note that prints two values does not keep the first."""
from __future__ import annotations

import sqlite3

import fitz

from pb_ceiling_lining_quantity import (
    explicit_ceiling_finish_descriptor,
    iter_explicit_ceiling_finish_matches,
)
from pb_document_joinery_head_height_authority import (
    JOINERY_HEAD_HEIGHT_CONFLICT,
    JOINERY_HEAD_HEIGHT_RESOLVED,
    DocumentJoineryHeadHeightProducer,
    _parse_joinery_head_height_mm,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_deduction_v175 import (
    derive_opening_deductions,
    parse_opening_dimensions,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_structural_member_authority import StructuralMemberSelector
from pb_structural_member_definition_producer import (
    SourceStructuralTextBlock,
    _member_role,
    _section_name,
    parse_structural_member_definitions,
)
from pb_surface_evidence_v160 import extract_finish_codes_from_positions


def test_one_ceiling_finish_stays_and_two_do_not() -> None:
    assert explicit_ceiling_finish_descriptor(
        "CEILING FINISH: 12mm gypsum plasterboard"
    ) == "12mm gypsum plasterboard"
    repeated = "ceiling finish plasterboard ceiling finish plasterboard"
    assert explicit_ceiling_finish_descriptor(repeated) == "plasterboard"
    conflict = "CEILING FINISH: plasterboard CEILING LINING: acoustic tile"
    assert explicit_ceiling_finish_descriptor(conflict) is None
    assert explicit_ceiling_finish_descriptor("ceiling finish as specified") is None
    assert [match.strip() for match in iter_explicit_ceiling_finish_matches(conflict)] == [
        "CEILING FINISH: plasterboard",
        "CEILING LINING: acoustic tile",
    ]


def test_one_joinery_head_height_stays_and_two_conflict() -> None:
    assert _parse_joinery_head_height_mm(
        "JOINERY HEIGHTS TO BE 2100 AFL U.N.O."
    ) == 2100.0
    assert _parse_joinery_head_height_mm(
        "JOINERY HEIGHTS TO BE 2100 AFL U.N.O. JOINERY HEIGHTS TO BE 2100 AFL U.N.O."
    ) == 2100.0
    assert _parse_joinery_head_height_mm(
        "JOINERY HEIGHTS TO BE 2100 AFL U.N.O. JOINERY HEIGHTS TO BE 2400 AFL U.N.O."
    ) is None

    doc = fitz.open()
    page = doc.new_page(width=500.0, height=300.0)
    page.insert_text(
        (40.0, 50.0),
        "JOINERY HEIGHTS TO BE 2100 AFL U.N.O. JOINERY HEIGHTS TO BE 2400 AFL U.N.O.",
        fontsize=9.0,
    )
    payload = bytes(doc.tobytes(garbage=4, deflate=True))
    doc.close()
    source = SourceVisibilityProducer(producer_method="one-note", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="joinery-head:one-note",
        source_bytes=payload,
        source_locator="fixture:one-note",
    )
    result = DocumentJoineryHeadHeightProducer.from_source_visibility_producer(
        source
    ).publish_revision(published.revision.revision_id)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.reason_codes == (JOINERY_HEAD_HEIGHT_CONFLICT,)
    assert result.evidence is None


def test_repeated_joinery_head_height_on_one_line_stays() -> None:
    doc = fitz.open()
    page = doc.new_page(width=500.0, height=300.0)
    page.insert_text(
        (40.0, 50.0),
        "JOINERY HEIGHTS TO BE 2100 AFL U.N.O. JOINERY HEIGHTS TO BE 2100 AFL U.N.O.",
        fontsize=9.0,
    )
    payload = bytes(doc.tobytes(garbage=4, deflate=True))
    doc.close()
    source = SourceVisibilityProducer(producer_method="one-note", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="joinery-head:repeated",
        source_bytes=payload,
        source_locator="fixture:repeated",
    )
    result = DocumentJoineryHeadHeightProducer.from_source_visibility_producer(
        source
    ).publish_revision(published.revision.revision_id)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (JOINERY_HEAD_HEIGHT_RESOLVED,)
    assert result.evidence is not None
    assert result.evidence.head_height_mm == 2100.0


def _selector() -> StructuralMemberSelector:
    return StructuralMemberSelector(
        document_id="source-document",
        revision_id="revision-1",
        source_sha256="a" * 64,
        snapshot_id="snapshot-1",
        decision_scope_id="building-a:frame",
        member_kind="structural_support",
    )


def _block(text: str) -> SourceStructuralTextBlock:
    return SourceStructuralTextBlock(
        page_id="201",
        view_id="structural-s201",
        block_id="member-1",
        reading_order=1,
        bbox=(50.0, 50.0, 400.0, 70.0),
        text=text,
        scope_id="building-a",
    )


def test_one_section_or_role_stays_and_two_do_not() -> None:
    assert _section_name("circular hollow sections") == "circular hollow section"
    assert _section_name("310UB40.4 beam") == "universal beam"
    assert _section_name("C15015 purlins") == "cold formed c section"
    assert _section_name("UB and UC beams") is None
    assert _member_role("100mm steel columns") == "column"
    assert _member_role("purlins") == "purlin"
    assert _member_role("columns and beams") is None

    one = parse_structural_member_definitions(
        selector=_selector(),
        blocks=(_block("310UB40.4 beam"),),
    )
    assert len(one) == 1
    assert one[0].definition.section_spec == "universal beam; 310ub40.4; beam"
    assert parse_structural_member_definitions(
        selector=_selector(),
        blocks=(_block("300 x 300mm and 400 x 400mm masonry piers"),),
    ) == ()
    assert parse_structural_member_definitions(
        selector=_selector(),
        blocks=(_block("C15015 universal beam"),),
    ) == ()


def test_one_opening_size_stays_and_two_sizes_or_counts_do_not() -> None:
    assert parse_opening_dimensions("Door D01 2040 x 820") == (2040.0, 820.0)
    assert parse_opening_dimensions("2040 x 820 or 2040 x 820") == (2040.0, 820.0)
    assert parse_opening_dimensions("2040 x 820 or 2100 x 910") is None
    assert parse_opening_dimensions("") == (2040.0, 820.0)

    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE register_items (
            id INTEGER PRIMARY KEY,
            workspace_id INTEGER,
            item_name TEXT,
            status TEXT
        );
        """
    )
    conn.executemany(
        "INSERT INTO register_items VALUES (?, 1, ?, 'Internal')",
        [
            (1, "Door D01 2040 x 820 Qty: 1"),
            (2, "Door D02 2040 x 820 or 2100 x 910 Qty: 1"),
            (3, "Door D03 2040 x 820 Qty: 1 Qty: 2"),
        ],
    )
    registry = derive_opening_deductions(conn, 1)
    assert [opening.opening_id for opening in registry.openings] == [1]


def test_one_finish_code_stays_and_two_in_one_word_do_not() -> None:
    words = [
        {"text": "PT01", "bbox": (0, 0, 10, 10)},
        {"text": "PT01 and PF02", "bbox": (20, 0, 80, 10)},
        {"text": "wet area FC01", "bbox": (90, 0, 140, 10)},
    ]
    assert [item["code"] for item in extract_finish_codes_from_positions(words)] == [
        "PT01",
        "FC01",
    ]
