"""Trusted source text may create structural definitions, never instances."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_structural_member_authority import (
    StructuralMemberProducer,
    StructuralMemberSelector,
)
from pb_structural_member_definition_source_shadow import (
    STRUCTURAL_DEFINITION_SOURCE_SHADOW_PAGE_UNAVAILABLE,
    STRUCTURAL_DEFINITION_SOURCE_SHADOW_RESOLVED,
    STRUCTURAL_DEFINITION_SOURCE_SHADOW_SCOPE_MISMATCH,
    _boq_commercial_columns,
    _is_ignorable_standalone_untrusted_marker,
    _is_ignorable_untrusted_commercial_cell,
    compile_structural_definition_source_shadow,
)


def _pdf_bytes(
    text: str = "Extra over for 300 x 300mm masonry piers, 4,500mm high",
    *,
    white_text: bool = False,
) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=500, height=300)
    page.insert_text(
        (72, 72),
        text,
        fontsize=10,
        fontname="helv",
        color=((1, 1, 1) if white_text else (0, 0, 0)),
    )
    payload = doc.tobytes()
    doc.close()
    return payload


def _ingest(payload: bytes, *, document_id: str = "structural-source-shadow"):
    producer = SourceVisibilityProducer(
        producer_method="structural-definition-source-shadow-test",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator=f"memory://{document_id}.pdf",
    )
    selector = StructuralMemberSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        decision_scope_id="source-page:1:unscoped",
        member_kind="structural_support",
    )
    return producer, published, selector


def test_trusted_source_words_compile_masonry_definition_without_quantity():
    producer, _published, selector = _ingest(_pdf_bytes())
    shadow = compile_structural_definition_source_shadow(
        selector=selector,
        source_visibility_producer=producer,
        page_ids=("1",),
    )

    assert shadow.status is EvidenceResolutionStatus.CORROBORATED
    assert STRUCTURAL_DEFINITION_SOURCE_SHADOW_RESOLVED in shadow.reason_codes
    assert len(shadow.definitions) == 1
    assert shadow.definitions[0].member_role == "pier"
    assert shadow.definitions[0].definition.section_spec == (
        "masonry; 300 x 300mm; pier"
    )
    assert shadow.blocks
    assert all(block.view_id == "source-page:1:unscoped" for block in shadow.blocks)
    assert shadow.trusted_text_observation_ids

    resolution = StructuralMemberProducer.from_authenticated_evidence(
        selector=selector,
        definitions=tuple(row.definition for row in shadow.definitions),
        observations=(),
        relations=(),
        view_scopes=(),
    ).publish()
    assert resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert resolution.quantity is None
    assert resolution.members == ()


def test_unrelated_dimension_text_does_not_become_structural_definition():
    producer, _published, selector = _ingest(
        _pdf_bytes("Window opening 300 x 300mm")
    )
    shadow = compile_structural_definition_source_shadow(
        selector=selector,
        source_visibility_producer=producer,
    )
    assert shadow.status is EvidenceResolutionStatus.ABSTAINED
    assert shadow.definitions == ()


def test_untrusted_hidden_text_does_not_become_structural_definition():
    producer, _published, selector = _ingest(
        _pdf_bytes(white_text=True),
        document_id="structural-source-shadow-hidden",
    )
    shadow = compile_structural_definition_source_shadow(
        selector=selector,
        source_visibility_producer=producer,
    )
    assert shadow.status is EvidenceResolutionStatus.ABSTAINED
    assert shadow.definitions == ()
    assert shadow.trusted_text_observation_ids == ()


def test_stale_source_lineage_fails_closed():
    producer, _published, selector = _ingest(_pdf_bytes())
    stale = StructuralMemberSelector(
        document_id=selector.document_id,
        revision_id=selector.revision_id,
        source_sha256="0" * 64,
        snapshot_id=selector.snapshot_id,
        decision_scope_id=selector.decision_scope_id,
        member_kind=selector.member_kind,
    )
    shadow = compile_structural_definition_source_shadow(
        selector=stale,
        source_visibility_producer=producer,
    )
    assert shadow.status is EvidenceResolutionStatus.CONFLICT
    assert shadow.reason_codes == (
        STRUCTURAL_DEFINITION_SOURCE_SHADOW_SCOPE_MISMATCH,
    )
    assert shadow.definitions == ()


def test_unavailable_page_fails_closed_without_cross_page_fallback():
    producer, _published, selector = _ingest(_pdf_bytes())
    shadow = compile_structural_definition_source_shadow(
        selector=selector,
        source_visibility_producer=producer,
        page_ids=("2",),
    )
    assert shadow.status is EvidenceResolutionStatus.ABSTAINED
    assert shadow.reason_codes == (
        STRUCTURAL_DEFINITION_SOURCE_SHADOW_PAGE_UNAVAILABLE,
    )
    assert shadow.blocks == ()
    assert shadow.definitions == ()


def test_replay_is_deterministic_and_does_not_mutate_source_snapshot():
    producer, published, selector = _ingest(_pdf_bytes())
    before = producer.published_snapshot_for_revision(selector.revision_id)
    first = compile_structural_definition_source_shadow(
        selector=selector,
        source_visibility_producer=producer,
    )
    second = compile_structural_definition_source_shadow(
        selector=selector,
        source_visibility_producer=producer,
    )
    after = producer.published_snapshot_for_revision(selector.revision_id)

    assert first == second
    assert before == published
    assert after == published


def test_shadow_adapter_is_not_wired_into_live_pdf_extractor():
    tree = ast.parse(Path("pb_planreader_pdf_extractor.py").read_text())
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    assert "pb_structural_member_definition_source_shadow" not in names


def test_shadow_module_has_no_benchmark_or_commercial_imports():
    tree = ast.parse(
        Path("pb_structural_member_definition_source_shadow.py").read_text()
    )
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    forbidden = ("benchmark", "gold", "jobhub", "takeoff")
    assert not any(
        any(token in name.lower() for token in forbidden)
        for name in names
    )



def _marker_receipt(
    *,
    raw_text="-",
    page_id="47",
    block_no=11,
    line_no=0,
    word_no=0,
):
    return SimpleNamespace(
        raw_text=raw_text,
        page_id=page_id,
        block_no=block_no,
        line_no=line_no,
        word_no=word_no,
    )


def test_only_source_isolated_decorative_marker_line_can_be_omitted():
    receipt = _marker_receipt()
    counts = {("47", 11, 0): 1}
    assert _is_ignorable_standalone_untrusted_marker(receipt, counts)


def test_marker_sharing_a_semantic_line_still_blocks_completeness():
    receipt = _marker_receipt()
    counts = {("47", 11, 0): 2}
    assert not _is_ignorable_standalone_untrusted_marker(receipt, counts)


def test_semantic_or_nonleading_untrusted_tokens_still_block_completeness():
    counts = {("47", 11, 0): 1}
    assert not _is_ignorable_standalone_untrusted_marker(
        _marker_receipt(raw_text="CHS"),
        counts,
    )
    assert not _is_ignorable_standalone_untrusted_marker(
        _marker_receipt(word_no=1),
        counts,
    )
    assert not _is_ignorable_standalone_untrusted_marker(
        _marker_receipt(line_no=None),
        counts,
    )



def _trusted_header_row(
    text,
    *,
    x0,
    x1,
    line_no,
    page_id="47",
    block_no=0,
):
    receipt = SimpleNamespace(
        raw_text=text,
        page_id=page_id,
        block_no=block_no,
        line_no=line_no,
        word_no=0,
        geometry=(x0, 10.0, x1, 20.0),
    )
    result = SimpleNamespace(
        status=EvidenceResolutionStatus.CORROBORATED,
        trusted_text=text,
    )
    return f"obs-{text}-{line_no}", result, receipt


def _complete_boq_header_rows():
    return [
        _trusted_header_row("Description", x0=100, x1=160, line_no=0),
        _trusted_header_row("Quantity", x0=200, x1=240, line_no=1),
        _trusted_header_row("Unit", x0=260, x1=280, line_no=2),
        _trusted_header_row("Rate", x0=300, x1=320, line_no=3),
        _trusted_header_row("Amount", x0=360, x1=400, line_no=4),
    ]


def _commercial_cell(
    text,
    *,
    x0,
    x1,
    line_no=4,
    word_no=0,
    y0=100.0,
):
    return SimpleNamespace(
        raw_text=text,
        page_id="47",
        block_no=12,
        line_no=line_no,
        word_no=word_no,
        geometry=(x0, y0, x1, y0 + 12.0),
    )


def test_complete_trusted_boq_header_proves_rate_and_amount_columns():
    columns = _boq_commercial_columns(_complete_boq_header_rows())
    assert set(columns) == {"47"}

    counts = {
        ("47", 12, 4): 1,
        ("47", 12, 5): 1,
    }
    assert _is_ignorable_untrusted_commercial_cell(
        _commercial_cell("2,200", x0=300, x1=330, line_no=4),
        counts,
        columns,
    )
    assert _is_ignorable_untrusted_commercial_cell(
        _commercial_cell("8,800", x0=370, x1=410, line_no=5),
        counts,
        columns,
    )


def test_quantity_or_semantic_numeric_text_is_not_ignored_as_commercial():
    columns = _boq_commercial_columns(_complete_boq_header_rows())
    counts = {
        ("47", 12, 2): 1,
        ("47", 12, 4): 1,
    }
    assert not _is_ignorable_untrusted_commercial_cell(
        _commercial_cell("4", x0=210, x1=230, line_no=2),
        counts,
        columns,
    )
    assert not _is_ignorable_untrusted_commercial_cell(
        _commercial_cell("2200mm", x0=300, x1=330, line_no=4),
        counts,
        columns,
    )


def test_commercial_cell_omission_requires_isolated_first_token_below_header():
    columns = _boq_commercial_columns(_complete_boq_header_rows())
    receipt = _commercial_cell("2,200", x0=300, x1=330, line_no=4)
    assert not _is_ignorable_untrusted_commercial_cell(
        receipt,
        {("47", 12, 4): 2},
        columns,
    )
    assert not _is_ignorable_untrusted_commercial_cell(
        _commercial_cell(
            "2,200",
            x0=300,
            x1=330,
            line_no=4,
            word_no=1,
        ),
        {("47", 12, 4): 1},
        columns,
    )
    assert not _is_ignorable_untrusted_commercial_cell(
        _commercial_cell(
            "2,200",
            x0=300,
            x1=330,
            line_no=4,
            y0=15.0,
        ),
        {("47", 12, 4): 1},
        columns,
    )


def test_incomplete_or_misordered_boq_header_proves_no_commercial_columns():
    incomplete = _complete_boq_header_rows()[:-1]
    assert _boq_commercial_columns(incomplete) == {}

    misordered = [
        _trusted_header_row("Description", x0=100, x1=160, line_no=0),
        _trusted_header_row("Quantity", x0=200, x1=240, line_no=1),
        _trusted_header_row("Unit", x0=260, x1=280, line_no=2),
        _trusted_header_row("Rate", x0=380, x1=400, line_no=3),
        _trusted_header_row("Amount", x0=300, x1=320, line_no=4),
    ]
    assert _boq_commercial_columns(misordered) == {}
