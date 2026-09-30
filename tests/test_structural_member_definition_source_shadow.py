"""Trusted source text may create structural definitions, never instances."""
from __future__ import annotations

import ast
from pathlib import Path

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
