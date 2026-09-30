from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import (
    ObservationSelector,
    SOURCE_HASH_MISMATCH,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_structural_member_authority import (
    StructuralMemberProducer,
    StructuralMemberSelector,
)
from pb_structural_member_physical_candidate_shadow import (
    COMPACT_MEMBER_SYMBOL_CANDIDATE,
    OUTLINED_VERTICAL_PROFILE_CANDIDATE,
    STRUCTURAL_PHYSICAL_CANDIDATE_SHADOW_PAGE_UNAVAILABLE,
    VERTICAL_PROFILE_CANDIDATE,
    StructuralPhysicalGeometryCandidate,
    _line_path_is_axis_aligned_rectangle,
    compile_structural_physical_candidate_shadow,
)


def _pdf_bytes(
    *,
    translate=(0.0, 0.0),
    scale=1.0,
    rotate_180=False,
    extra_wide=False,
):
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)

    def point(x, y):
        x = x * scale + translate[0]
        y = y * scale + translate[1]
        if rotate_180:
            x, y = 400 - x, 400 - y
        return x, y

    def rect(x0, y0, x1, y1):
        a = point(x0, y0)
        b = point(x1, y1)
        return fitz.Rect(
            min(a[0], b[0]),
            min(a[1], b[1]),
            max(a[0], b[0]),
            max(a[1], b[1]),
        )

    page.draw_rect(
        rect(20, 20, 24, 24),
        color=(0, 0, 0),
        fill=(0, 0, 0),
    )
    page.draw_rect(
        rect(80, 30, 90, 150),
        color=(0, 0, 0),
    )
    page.draw_rect(
        rect(120, 30, 130, 150),
        color=(0, 0, 0),
        fill=(0, 0, 0),
    )
    page.draw_rect(
        rect(180, 30, 300, 40),
        color=(0, 0, 0),
    )

    if extra_wide:
        page.draw_rect(
            rect(40, 300, 300, 310),
            color=(0, 0, 0),
        )

    payload = doc.tobytes()
    doc.close()
    return payload


def _ingest(payload):
    producer = SourceVisibilityProducer(
        producer_method="structural-physical-candidate-shadow-test",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="structural-candidate-shadow",
        source_bytes=payload,
        source_locator="memory://structural-candidate-shadow.pdf",
    )
    return producer, published


def _compile(payload, *, page_ids=("1",)):
    producer, published = _ingest(payload)
    result = compile_structural_physical_candidate_shadow(
        source_visibility_producer=producer,
        revision_id=published.revision.revision_id,
        source_bytes=payload,
        page_ids=page_ids,
    )
    return producer, published, result


def test_neutral_candidate_classes_are_source_visible_and_semantics_free():
    payload = _pdf_bytes()
    producer, published, result = _compile(payload)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    classes = [row.candidate_class for row in result.candidates]
    assert COMPACT_MEMBER_SYMBOL_CANDIDATE in classes
    assert OUTLINED_VERTICAL_PROFILE_CANDIDATE in classes
    assert VERTICAL_PROFILE_CANDIDATE in classes
    assert len(result.candidates) == 3

    visible_ids = set(published.visible_observation_ids)
    authority = producer.authority()
    for candidate in result.candidates:
        assert candidate.view_id is None
        assert candidate.source_observation_ids
        assert set(candidate.source_observation_ids) <= visible_ids
        assert candidate.source_primitive_refs
        for observation_id in candidate.source_observation_ids:
            resolution = authority.resolve_visible(
                ObservationSelector(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    observation_id=observation_id,
                )
            )
            assert resolution.status is EvidenceResolutionStatus.CORROBORATED
            assert resolution.observation is not None

    field_names = {field.name for field in fields(StructuralPhysicalGeometryCandidate)}
    assert "member_kind" not in field_names
    assert "definition_id" not in field_names
    assert "quantity" not in field_names
    assert "complete" not in field_names


def test_wide_shallow_rectangles_are_lookalike_negatives():
    payload = _pdf_bytes(extra_wide=True)
    _producer, _published, result = _compile(payload)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert all(row.height > row.width or row.orientation == "compact" for row in result.candidates)
    assert not any(
        row.width >= 100 and row.height <= 20
        for row in result.candidates
    )


def test_hash_mismatch_and_unavailable_page_fail_closed():
    payload = _pdf_bytes()
    producer, published = _ingest(payload)

    mismatch = compile_structural_physical_candidate_shadow(
        source_visibility_producer=producer,
        revision_id=published.revision.revision_id,
        source_bytes=payload + b"tampered",
        page_ids=("1",),
    )
    assert mismatch.status is EvidenceResolutionStatus.CONFLICT
    assert mismatch.reason_codes == (SOURCE_HASH_MISMATCH,)
    assert mismatch.candidates == ()

    unavailable = compile_structural_physical_candidate_shadow(
        source_visibility_producer=producer,
        revision_id=published.revision.revision_id,
        source_bytes=payload,
        page_ids=("2",),
    )
    assert unavailable.status is EvidenceResolutionStatus.ABSTAINED
    assert unavailable.reason_codes == (
        STRUCTURAL_PHYSICAL_CANDIDATE_SHADOW_PAGE_UNAVAILABLE,
    )
    assert unavailable.candidates == ()


def test_replay_is_deterministic_and_does_not_mutate_published_snapshot():
    payload = _pdf_bytes()
    producer, published = _ingest(payload)
    before = producer.published_snapshot_for_revision(
        published.revision.revision_id
    )

    first = compile_structural_physical_candidate_shadow(
        source_visibility_producer=producer,
        revision_id=published.revision.revision_id,
        source_bytes=payload,
    )
    second = compile_structural_physical_candidate_shadow(
        source_visibility_producer=producer,
        revision_id=published.revision.revision_id,
        source_bytes=payload,
    )
    after = producer.published_snapshot_for_revision(
        published.revision.revision_id
    )

    assert first == second
    assert before == published
    assert after == published
    assert payload == bytes(payload)


def test_translation_scale_and_180_rotation_preserve_geometry_classes():
    variants = (
        _pdf_bytes(),
        _pdf_bytes(translate=(5.0, 5.0), scale=1.05),
        _pdf_bytes(rotate_180=True),
    )
    observed = []
    for payload in variants:
        _producer, _published, result = _compile(payload)
        observed.append(sorted(row.candidate_class for row in result.candidates))

    assert observed[0] == observed[1] == observed[2]
    assert observed[0] == sorted(
        (
            COMPACT_MEMBER_SYMBOL_CANDIDATE,
            OUTLINED_VERTICAL_PROFILE_CANDIDATE,
            VERTICAL_PROFILE_CANDIDATE,
        )
    )


def test_line_outline_segment_splitting_and_order_are_invariant():
    unsplit = (
        {"x1": 10.0, "y1": 10.0, "x2": 20.0, "y2": 10.0},
        {"x1": 20.0, "y1": 10.0, "x2": 20.0, "y2": 100.0},
        {"x1": 20.0, "y1": 100.0, "x2": 10.0, "y2": 100.0},
        {"x1": 10.0, "y1": 100.0, "x2": 10.0, "y2": 10.0},
    )
    split = (
        {"x1": 10.0, "y1": 10.0, "x2": 15.0, "y2": 10.0},
        {"x1": 15.0, "y1": 10.0, "x2": 20.0, "y2": 10.0},
        {"x1": 20.0, "y1": 10.0, "x2": 20.0, "y2": 55.0},
        {"x1": 20.0, "y1": 55.0, "x2": 20.0, "y2": 100.0},
        {"x1": 20.0, "y1": 100.0, "x2": 15.0, "y2": 100.0},
        {"x1": 15.0, "y1": 100.0, "x2": 10.0, "y2": 100.0},
        {"x1": 10.0, "y1": 100.0, "x2": 10.0, "y2": 55.0},
        {"x1": 10.0, "y1": 55.0, "x2": 10.0, "y2": 10.0},
    )
    diagonal = unsplit[:-1] + (
        {"x1": 10.0, "y1": 100.0, "x2": 11.0, "y2": 10.0},
    )

    assert _line_path_is_axis_aligned_rectangle(unsplit)
    assert _line_path_is_axis_aligned_rectangle(tuple(reversed(unsplit)))
    assert _line_path_is_axis_aligned_rectangle(split)
    assert _line_path_is_axis_aligned_rectangle(tuple(reversed(split)))
    assert not _line_path_is_axis_aligned_rectangle(diagonal)


def test_candidates_do_not_create_members_completeness_or_quantity():
    payload = _pdf_bytes()
    _producer, published, candidates = _compile(payload)
    assert candidates.candidates

    selector = StructuralMemberSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        decision_scope_id="source-page:1:unscoped",
        member_kind="structural_support",
    )
    resolution = StructuralMemberProducer.from_authenticated_evidence(
        selector=selector,
        definitions=(),
        observations=(),
        relations=(),
        view_scopes=(),
    ).publish()

    assert resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert resolution.quantity is None
    assert resolution.members == ()


def test_shadow_module_is_not_wired_into_live_structural_or_pdf_extractors():
    paths = (
        Path("pb_planreader_pdf_extractor.py"),
        Path("pb_structural_member_authority.py"),
        Path("pb_structural_member_registration_producer.py"),
        Path("pb_secondary_support_structural_member_adapter.py"),
    )
    for path in paths:
        tree = ast.parse(path.read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        assert "pb_structural_member_physical_candidate_shadow" not in imports


def test_shadow_module_has_no_benchmark_or_commercial_dependencies():
    tree = ast.parse(
        Path("pb_structural_member_physical_candidate_shadow.py").read_text()
    )
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    forbidden = ("benchmark", "gold", "jobhub", "takeoff")
    assert not any(
        any(token in name.lower() for token in forbidden)
        for name in imports
    )
