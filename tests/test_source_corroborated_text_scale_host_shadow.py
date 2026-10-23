"""Shadow compiler for corroborated words, unique graphic block-bar scale, unique primitive hosts."""
from __future__ import annotations

import copy

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_scale_block_bar_shadow import MM_PER_POINT_AT_1_TO_1
from pb_source_corroborated_text_scale_host_shadow import (
    GRAPHIC_SCALE_CANDIDATE,
    GRAPHIC_SCALE_CONFLICT,
    GRAPHIC_SCALE_UNAVAILABLE,
    HOST_PRIMITIVE_AMBIGUOUS,
    HOST_PRIMITIVE_CANDIDATE,
    HOST_PRIMITIVE_UNMAPPED,
    METHOD_AMORTIZED_GLYPH,
    METHOD_DIRECT_OCR,
    METHOD_TRUSTED_PDF_TEXT,
    OPENING_LABEL_AMBIGUOUS,
    OPENING_LABEL_CANDIDATE,
    OPENING_LABEL_UNAVAILABLE,
    SOURCE_TEXT_UNUSABLE,
    CorroboratedNativeWord,
    ShadowHostWall,
    compile_corroborated_text_scale_host,
    resolve_graphic_block_bar_scale,
    resolve_opening_label_from_corroborated_text,
    resolve_primitive_owned_opening_host,
)

STEP_PT = 10 / MM_PER_POINT_AT_1_TO_1


def _word(oid: str, text: str, cx: float, cy: float, method: str = METHOD_AMORTIZED_GLYPH, w: float = 8.0, h: float = 6.0):
    return CorroboratedNativeWord(
        observation_id=oid,
        text=text,
        bbox=(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2),
        method=method,
    )


def _edge(ident: str, x: float, y_lo: float, y_hi: float):
    return {"id": ident, "x1": x, "y1": y_lo, "x2": x, "y2": y_hi}


def _horizontal_bar(x0: float = 100.0, y: float = 760.0, n: int = 10):
    words = []
    segs = []
    for k in range(n + 1):
        text = str(k) if k < n else f"{k}m"
        words.append(_word(f"w{k}", text, x0 + k * STEP_PT, y))
        segs.append(_edge(f"e{k}", x0 + k * STEP_PT, y - 12.0, y - 6.0))
    return segs, words


def test_rotated_vertical_block_bar_is_measured_in_native_frame():
    words = []
    segs = []
    y0 = 100.0
    x = 760.0
    for k in range(11):
        text = str(k) if k < 10 else "10m"
        words.append(_word(f"v{k}", text, x, y0 + k * STEP_PT))
        segs.append(
            {"id": f"ve{k}", "x1": x - 12.0, "y1" : y0 + k * STEP_PT, "x2": x - 6.0, "y2": y0 + k * STEP_PT}
        )
    result = resolve_graphic_block_bar_scale(segs, words)
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.payload["axis"] == "y"
    assert result.payload["points_per_mm"] == pytest.approx(
        1.0 / (MM_PER_POINT_AT_1_TO_1 * 100.0), rel=1e-6
    )


def test_unique_block_bar_from_corroborated_numerals_is_candidate_not_firm():
    segs, words = _horizontal_bar()
    result = resolve_graphic_block_bar_scale(segs, words)
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert GRAPHIC_SCALE_CANDIDATE in result.reason_codes
    assert result.takeoff_eligible is False
    assert result.commercial_projection_allowed is False
    assert result.payload["scale_authority_granted"] is False
    assert result.payload["points_per_mm"] == pytest.approx(1.0 / (MM_PER_POINT_AT_1_TO_1 * 100.0), rel=1e-6)


def test_uncorroborated_page_has_no_scale():
    segs, _words = _horizontal_bar()
    result = resolve_graphic_block_bar_scale(segs, ())
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert SOURCE_TEXT_UNUSABLE in result.reason_codes


def test_numerals_without_block_edges_are_not_a_bar():
    _segs, words = _horizontal_bar()
    result = resolve_graphic_block_bar_scale((), words)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert GRAPHIC_SCALE_UNAVAILABLE in result.reason_codes


def test_two_disagreeing_bars_conflict_and_retain_both():
    segs_a, words_a = _horizontal_bar(x0=100.0, y=100.0)
    segs_b, words_b = _horizontal_bar(x0=100.0, y=400.0, n=5)
    # Second bar uses same step but only 5 m span at the same pt spacing → same ppm.
    # Build a truly disagreeing bar: double spacing.
    words_b = []
    segs_b = []
    for k in range(6):
        text = str(k) if k < 5 else "5m"
        words_b.append(_word(f"b{k}", text, 100.0 + k * (STEP_PT * 2), 400.0))
        segs_b.append(_edge(f"be{k}", 100.0 + k * (STEP_PT * 2), 388.0, 394.0))
    result = resolve_graphic_block_bar_scale(segs_a + segs_b, words_a + words_b)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert GRAPHIC_SCALE_CONFLICT in result.reason_codes
    assert result.payload["candidate_count"] == 2


def test_title_block_ratio_alone_is_not_a_scale():
    words = [_word("r", "1:100", 600.0, 790.0, method=METHOD_TRUSTED_PDF_TEXT, w=24.0)]
    result = resolve_graphic_block_bar_scale((), words)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert GRAPHIC_SCALE_UNAVAILABLE in result.reason_codes


def test_unique_opening_label_from_corroborated_callout():
    opening = (0.0, 0.0, 80.0, 40.0)
    words = [
        _word("lab", "1200-1810 ASW", 40.0, 20.0, method=METHOD_DIRECT_OCR, w=40.0, h=10.0),
        _word("noise", "KITCHEN", 200.0, 200.0),
    ]
    result = resolve_opening_label_from_corroborated_text(opening, words)
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert OPENING_LABEL_CANDIDATE in result.reason_codes
    assert result.payload["dimension_values_mm"] == (1200.0, 1810.0)
    assert result.payload["axis_order_resolved"] is False
    assert result.takeoff_eligible is False


def test_two_different_labels_on_one_opening_conflict():
    opening = (0.0, 0.0, 200.0, 80.0)
    words = [
        _word("a", "1200-1810 ASW", 40.0, 20.0, w=40.0, h=10.0),
        _word("b", "1800-2410 ASW", 140.0, 20.0, w=40.0, h=10.0),
    ]
    result = resolve_opening_label_from_corroborated_text(opening, words)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert OPENING_LABEL_AMBIGUOUS in result.reason_codes
    assert result.payload["parseable_count"] == 2


def test_label_outside_opening_does_not_bind():
    opening = (0.0, 0.0, 40.0, 20.0)
    words = [_word("lab", "1200-1810 ASW", 400.0, 400.0, w=40.0, h=10.0)]
    result = resolve_opening_label_from_corroborated_text(opening, words)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert OPENING_LABEL_UNAVAILABLE in result.reason_codes


def test_furniture_note_is_not_an_opening_label():
    opening = (0.0, 0.0, 80.0, 40.0)
    words = [_word("n", "TABLE", 40.0, 20.0)]
    result = resolve_opening_label_from_corroborated_text(opening, words)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert OPENING_LABEL_UNAVAILABLE in result.reason_codes


def test_unique_two_wall_primitive_host_is_candidate():
    walls = [
        ShadowHostWall("wall-a", ("p1", "p2", "other")),
        ShadowHostWall("wall-b", ("p3", "p4")),
        ShadowHostWall("wall-c", ("unrelated",)),
    ]
    result = resolve_primitive_owned_opening_host(("p1", "p2", "p3", "p4"), walls)
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert HOST_PRIMITIVE_CANDIDATE in result.reason_codes
    assert result.payload["host_wall_ids"] == ("wall-a", "wall-b")
    assert result.takeoff_eligible is False


def test_page_wide_ambiguous_id_does_not_veto_unique_primitive_owners():
    # wall-a would be page-wide ambiguous with some distant parallel path; primitives still unique.
    walls = [
        ShadowHostWall("wall-a", ("p1", "p2")),
        ShadowHostWall("wall-b", ("p3", "p4")),
    ]
    result = resolve_primitive_owned_opening_host(("p4", "p1", "p3", "p2"), walls)
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.payload["host_wall_ids"] == ("wall-a", "wall-b")


def test_shared_primitive_two_owners_conflict_and_retain_both():
    walls = [
        ShadowHostWall("wall-a", ("p1", "p2")),
        ShadowHostWall("wall-b", ("p3", "p4")),
        ShadowHostWall("wall-c", ("p1",)),
    ]
    result = resolve_primitive_owned_opening_host(("p1", "p2", "p3", "p4"), walls)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert HOST_PRIMITIVE_AMBIGUOUS in result.reason_codes
    assert "p1" in result.payload["contested_primitive_ids"]


def test_missing_primitive_owner_abstains():
    walls = [ShadowHostWall("wall-a", ("p1", "p2", "p3"))]
    result = resolve_primitive_owned_opening_host(("p1", "p2", "p3", "p4"), walls)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert HOST_PRIMITIVE_UNMAPPED in result.reason_codes
    assert result.payload["unmapped_primitive_ids"] == ("p4",)


def test_w7_style_empty_gap_is_not_a_host():
    result = resolve_primitive_owned_opening_host((), ())
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert HOST_PRIMITIVE_UNMAPPED in result.reason_codes


def test_input_order_and_translation_invariance():
    segs, words = _horizontal_bar()
    opening = (0.0, 0.0, 80.0, 40.0)
    labels = [_word("lab", "870 CS", 20.0, 10.0, w=20.0, h=8.0)]
    walls = [
        ShadowHostWall("wall-b", ("p3", "p4")),
        ShadowHostWall("wall-a", ("p1", "p2")),
    ]
    base = compile_corroborated_text_scale_host(
        segments=segs,
        words=words + labels,
        opening_bbox=opening,
        face_primitive_ids=("p1", "p2", "p3", "p4"),
        walls=walls,
    )
    shuffled_words = list(reversed(words + labels))
    shuffled_segs = list(reversed(segs))
    shuffled_walls = list(reversed(walls))
    again = compile_corroborated_text_scale_host(
        segments=shuffled_segs,
        words=shuffled_words,
        opening_bbox=opening,
        face_primitive_ids=("p4", "p3", "p2", "p1"),
        walls=shuffled_walls,
    )
    assert base.status is EvidenceResolutionStatus.CANDIDATE
    assert again.status is EvidenceResolutionStatus.CANDIDATE
    assert again.payload["host"]["host_wall_ids"] == base.payload["host"]["host_wall_ids"]
    assert again.payload["scale"]["points_per_mm"] == pytest.approx(
        base.payload["scale"]["points_per_mm"]
    )

    dx, dy = 40.0, -15.0
    moved_segs = [
        {
            "id": s["id"],
            "x1": s["x1"] + dx,
            "y1": s["y1"] + dy,
            "x2": s["x2"] + dx,
            "y2": s["y2"] + dy,
        }
        for s in segs
    ]
    moved_words = [
        CorroboratedNativeWord(
            observation_id=w.observation_id,
            text=w.text,
            bbox=(w.bbox[0] + dx, w.bbox[1] + dy, w.bbox[2] + dx, w.bbox[3] + dy),
            method=w.method,
        )
        for w in words + labels
    ]
    moved_opening = (opening[0] + dx, opening[1] + dy, opening[2] + dx, opening[3] + dy)
    moved = compile_corroborated_text_scale_host(
        segments=moved_segs,
        words=moved_words,
        opening_bbox=moved_opening,
        face_primitive_ids=("p1", "p2", "p3", "p4"),
        walls=walls,
    )
    assert moved.status is EvidenceResolutionStatus.CANDIDATE
    assert moved.payload["scale"]["points_per_mm"] == pytest.approx(
        base.payload["scale"]["points_per_mm"]
    )


def test_scale_metamorphic_doubling_halves_points_per_mm_ratio_inverse():
    segs, words = _horizontal_bar()
    base = resolve_graphic_block_bar_scale(segs, words)
    scaled_segs = [
        {"id": s["id"], "x1": s["x1"] * 2, "y1": s["y1"], "x2": s["x2"] * 2, "y2": s["y2"]}
        for s in segs
    ]
    scaled_words = [
        CorroboratedNativeWord(
            observation_id=w.observation_id,
            text=w.text,
            bbox=(w.bbox[0] * 2, w.bbox[1], w.bbox[2] * 2, w.bbox[3]),
            method=w.method,
        )
        for w in words
    ]
    scaled = resolve_graphic_block_bar_scale(scaled_segs, scaled_words)
    assert scaled.status is EvidenceResolutionStatus.CANDIDATE
    assert scaled.payload["points_per_mm"] == pytest.approx(
        base.payload["points_per_mm"] * 2, rel=1e-6
    )


def test_no_mutation_of_inputs():
    segs, words = _horizontal_bar()
    opening = (0.0, 0.0, 80.0, 40.0)
    labels = [_word("lab", "1200-1810 ASW", 20.0, 10.0, w=30.0, h=8.0)]
    walls = [
        ShadowHostWall("wall-a", ("p1", "p2")),
        ShadowHostWall("wall-b", ("p3", "p4")),
    ]
    segs_copy = copy.deepcopy(segs)
    words_copy = copy.deepcopy(list(words + labels))
    walls_copy = copy.deepcopy(list(walls))
    compile_corroborated_text_scale_host(
        segments=segs,
        words=words + labels,
        opening_bbox=opening,
        face_primitive_ids=["p1", "p2", "p3", "p4"],
        walls=walls,
    )
    assert segs == segs_copy
    assert words + labels == words_copy
    assert walls == walls_copy


def test_unrelated_content_does_not_steal_unique_bar_or_host():
    segs, words = _horizontal_bar()
    extra_words = words + [
        _word("note", "N.T.S.", 900.0, 20.0, method=METHOD_TRUSTED_PDF_TEXT),
        _word("lab", "1200-1810 ASW", 20.0, 10.0, w=30.0, h=8.0),
    ]
    extra_segs = segs + [_edge("furniture", 12.0, 12.0, 18.0)]
    result = compile_corroborated_text_scale_host(
        segments=extra_segs,
        words=extra_words,
        opening_bbox=(0.0, 0.0, 80.0, 40.0),
        face_primitive_ids=("p1", "p2", "p3", "p4"),
        walls=[
            ShadowHostWall("wall-a", ("p1", "p2")),
            ShadowHostWall("wall-b", ("p3", "p4")),
            ShadowHostWall("furniture", ("table-loop",)),
        ],
    )
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.payload["host"]["host_wall_ids"] == ("wall-a", "wall-b")


def test_deterministic_replay_stable_ids():
    segs, words = _horizontal_bar()
    first = resolve_graphic_block_bar_scale(segs, words)
    second = resolve_graphic_block_bar_scale(segs, words)
    assert first.payload["record_id"] == second.payload["record_id"]
    assert first.payload["record_id"]


def test_first_failing_gate_stops_at_scale_before_host():
    result = compile_corroborated_text_scale_host(
        segments=(),
        words=(_word("lab", "1200-1810 ASW", 20.0, 10.0, w=30.0, h=8.0),),
        opening_bbox=(0.0, 0.0, 80.0, 40.0),
        face_primitive_ids=("p1", "p2", "p3", "p4"),
        walls=[ShadowHostWall("wall-a", ("p1", "p2", "p3", "p4"))],
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert GRAPHIC_SCALE_UNAVAILABLE in result.reason_codes
    assert "host" not in result.payload
