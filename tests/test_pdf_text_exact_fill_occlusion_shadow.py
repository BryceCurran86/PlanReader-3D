from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

from pb_migration_contracts import EvidenceResolutionStatus
from pb_pdf_text_exact_fill_occlusion_shadow import (
    SHADOW_DRAWING_OWNERSHIP_UNRESOLVED,
    SHADOW_EXACT_FILL_CLEAR,
    SHADOW_EXACT_FILL_OCCLUSION,
    SHADOW_NON_FILL_OCCLUDER,
    SHADOW_OVERLAPPING_RECTANGLES,
    SHADOW_UNSUPPORTED_FILL_GEOMETRY,
    TEXT_NOT_OCCLUDED_BY_LATER_PAINT,
    resolve_later_paint_occlusion_shadow,
)
from pb_pdf_text_integrity_authority import TEXT_OCCLUDED_BY_LATER_PAINT


class FakePage:
    def __init__(self, bboxlog, drawings):
        self.bboxlog = deepcopy(bboxlog)
        self.drawings = deepcopy(drawings)

    def get_bboxlog(self):
        return deepcopy(self.bboxlog)

    def get_drawings(self, *, extended=False):
        assert extended is True
        return deepcopy(self.drawings)


def fill_rectangles(seqno, rectangles, *, drawing_type="f", fill=(0.0, 0.0, 0.0)):
    return {
        "seqno": seqno,
        "type": drawing_type,
        "fill": fill,
        "items": tuple(("re", rect, 1) for rect in rectangles),
    }


def test_disconnected_rectangles_do_not_occlude_via_aggregate_bbox():
    subject = (40.0, 40.0, 60.0, 50.0)
    page = FakePage(
        bboxlog=(
            ("fill-text", subject),
            ("fill-path", (0.0, 0.0, 100.0, 100.0)),
        ),
        drawings=(
            fill_rectangles(
                1,
                (
                    (0.0, 0.0, 10.0, 10.0),
                    (90.0, 0.0, 100.0, 10.0),
                    (0.0, 90.0, 10.0, 100.0),
                    (90.0, 90.0, 100.0, 100.0),
                ),
            ),
        ),
    )

    result = resolve_later_paint_occlusion_shadow(page, subject, 0)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proposition == TEXT_NOT_OCCLUDED_BY_LATER_PAINT
    assert result.reason_codes == (SHADOW_EXACT_FILL_CLEAR,)
    assert result.current_bbox_candidate_count == 1
    assert result.exact_fill_path_count == 1
    assert result.max_exact_coverage_ratio == 0.0
    assert result.evaluated_fill_sequence_numbers == (1,)
    assert result.shadow_id == (
        "pdf_text_exact_fill_occlusion_shadow_"
        "52fcf2ab2190e743e62f3e66d99aadd6"
    )


def test_actual_rectangle_union_covering_threshold_remains_occlusion():
    subject = (0.0, 0.0, 100.0, 20.0)
    page = FakePage(
        bboxlog=(
            ("fill-text", subject),
            ("fill-path", (0.0, 0.0, 100.0, 20.0)),
        ),
        drawings=(
            fill_rectangles(
                1,
                (
                    (0.0, 0.0, 40.0, 20.0),
                    (40.0, 0.0, 70.0, 20.0),
                ),
            ),
        ),
    )

    result = resolve_later_paint_occlusion_shadow(page, subject, 0)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proposition == TEXT_OCCLUDED_BY_LATER_PAINT
    assert result.reason_codes == (SHADOW_EXACT_FILL_OCCLUSION,)
    assert result.max_exact_coverage_ratio == 0.7


def test_real_opaque_full_rectangle_stays_blocked():
    subject = (10.0, 10.0, 30.0, 20.0)
    page = FakePage(
        bboxlog=(
            ("fill-text", subject),
            ("fill-path", subject),
        ),
        drawings=(fill_rectangles(1, (subject,)),),
    )

    result = resolve_later_paint_occlusion_shadow(page, subject, 0)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proposition == TEXT_OCCLUDED_BY_LATER_PAINT
    assert result.max_exact_coverage_ratio == 1.0


def test_overlapping_rectangle_items_fail_closed():
    subject = (0.0, 0.0, 100.0, 20.0)
    page = FakePage(
        bboxlog=(
            ("fill-text", subject),
            ("fill-path", subject),
        ),
        drawings=(
            fill_rectangles(
                1,
                (
                    (0.0, 0.0, 70.0, 20.0),
                    (30.0, 0.0, 100.0, 20.0),
                ),
            ),
        ),
    )

    result = resolve_later_paint_occlusion_shadow(page, subject, 0)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.proposition is None
    assert SHADOW_OVERLAPPING_RECTANGLES in result.reason_codes


def test_mixed_path_geometry_fails_closed():
    subject = (0.0, 0.0, 100.0, 20.0)
    drawing = fill_rectangles(1, ((0.0, 0.0, 20.0, 20.0),))
    drawing["items"] = (
        ("re", (0.0, 0.0, 20.0, 20.0), 1),
        ("l", (20.0, 0.0), (80.0, 20.0)),
    )
    page = FakePage(
        bboxlog=(
            ("fill-text", subject),
            ("fill-path", subject),
        ),
        drawings=(drawing,),
    )

    result = resolve_later_paint_occlusion_shadow(page, subject, 0)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert SHADOW_UNSUPPORTED_FILL_GEOMETRY in result.reason_codes


def test_duplicate_drawing_ownership_fails_closed():
    subject = (0.0, 0.0, 100.0, 20.0)
    drawing = fill_rectangles(1, ((0.0, 0.0, 20.0, 20.0),))
    page = FakePage(
        bboxlog=(
            ("fill-text", subject),
            ("fill-path", subject),
        ),
        drawings=(drawing, deepcopy(drawing)),
    )

    result = resolve_later_paint_occlusion_shadow(page, subject, 0)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert SHADOW_DRAWING_OWNERSHIP_UNRESOLVED in result.reason_codes


def test_non_fill_later_occluder_is_not_reinterpreted():
    subject = (0.0, 0.0, 100.0, 20.0)
    page = FakePage(
        bboxlog=(
            ("fill-text", subject),
            ("fill-image", subject),
        ),
        drawings=(),
    )

    result = resolve_later_paint_occlusion_shadow(page, subject, 0)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.proposition is None
    assert SHADOW_NON_FILL_OCCLUDER in result.reason_codes


def test_translation_and_scale_preserve_exact_coverage_decision():
    base_subject = (10.0, 10.0, 30.0, 20.0)
    base_rectangles = (
        (0.0, 0.0, 5.0, 5.0),
        (40.0, 25.0, 50.0, 35.0),
    )

    def transform(rect, scale, dx, dy):
        x0, y0, x1, y1 = rect
        return (
            x0 * scale + dx,
            y0 * scale + dy,
            x1 * scale + dx,
            y1 * scale + dy,
        )

    results = []
    for scale, dx, dy in ((1.0, 0.0, 0.0), (3.5, 200.0, -80.0)):
        subject = transform(base_subject, scale, dx, dy)
        rectangles = tuple(
            transform(rect, scale, dx, dy)
            for rect in base_rectangles
        )
        page = FakePage(
            bboxlog=(
                ("fill-text", subject),
                (
                    "fill-path",
                    transform((0.0, 0.0, 50.0, 35.0), scale, dx, dy),
                ),
            ),
            drawings=(fill_rectangles(1, rectangles),),
        )
        results.append(
            resolve_later_paint_occlusion_shadow(page, subject, 0)
        )

    assert [row.proposition for row in results] == [
        TEXT_NOT_OCCLUDED_BY_LATER_PAINT,
        TEXT_NOT_OCCLUDED_BY_LATER_PAINT,
    ]
    assert [row.max_exact_coverage_ratio for row in results] == [0.0, 0.0]


def test_replay_and_drawing_input_order_are_deterministic_and_non_mutating():
    subject = (40.0, 40.0, 60.0, 50.0)
    relevant = fill_rectangles(
        2,
        (
            (0.0, 0.0, 10.0, 10.0),
            (90.0, 90.0, 100.0, 100.0),
        ),
    )
    irrelevant = fill_rectangles(9, ((0.0, 0.0, 5.0, 5.0),))
    bboxlog = (
        ("fill-text", subject),
        ("stroke-path", (0.0, 0.0, 1.0, 1.0)),
        ("fill-path", (0.0, 0.0, 100.0, 100.0)),
    )

    page_a = FakePage(bboxlog, (relevant, irrelevant))
    page_b = FakePage(bboxlog, (irrelevant, relevant))
    before_a = (deepcopy(page_a.bboxlog), deepcopy(page_a.drawings))
    before_b = (deepcopy(page_b.bboxlog), deepcopy(page_b.drawings))

    first = resolve_later_paint_occlusion_shadow(page_a, subject, 0)
    replay = resolve_later_paint_occlusion_shadow(page_a, subject, 0)
    reordered = resolve_later_paint_occlusion_shadow(page_b, subject, 0)

    assert first == replay == reordered
    assert before_a == (page_a.bboxlog, page_a.drawings)
    assert before_b == (page_b.bboxlog, page_b.drawings)


def test_shadow_module_is_not_imported_by_live_text_or_pdf_extractors():
    for path in (
        Path("pb_pdf_text_integrity_authority.py"),
        Path("pb_planreader_pdf_extractor.py"),
    ):
        tree = ast.parse(path.read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        assert "pb_pdf_text_exact_fill_occlusion_shadow" not in imports
